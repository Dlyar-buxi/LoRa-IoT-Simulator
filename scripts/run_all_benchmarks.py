#!/usr/bin/env python3
"""Sprint 6.2.1 / v1.2 T14 — Unified LoRa Benchmark Suite runner.

Orchestrates the three Sprint 6.1 experiments end-to-end and aggregates
their outputs under ``docs/benchmark/``.  This is a thin outer-layer
wrapper only: it does NOT import or modify the frozen core
(``simulator/``, ``gateway/``, ``backend/``) and it does NOT refactor the
existing per-benchmark scripts — it simply runs each one via subprocess
with the repository root as the working directory so their relative
output paths (``docs/benchmark/...``) resolve correctly.

Usage (from anywhere inside the repo):
    python scripts/run_all_benchmarks.py
    python scripts/run_all_benchmarks.py --report-json bench_report.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import tracemalloc
from typing import Any

# Unix-only resource module. Windows 下用 psutil fallback；在 helper 内部按可用性分支。
try:
    import resource as _resource  # type: ignore[attr-defined]
except ImportError:  # Windows / non-Unix
    _resource = None  # type: ignore[assignment]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCHMARK_DIR = os.path.join(REPO_ROOT, "scripts", "benchmark")

# (display label, script filename) — executed in this fixed order
STAGES = [
    ("Scalability Benchmark", "run_scalability.py"),
    ("ADR Comparison", "run_adr_compare.py"),
    ("Distance Curve", "run_distance.py"),
]

# Reuse the interpreter that launched this runner so the matplotlib /
# numpy / pandas dependencies installed for it are available to children.
PYTHON = sys.executable

RESULTS_DIR = os.path.join(REPO_ROOT, "docs", "benchmark")


# ---------------------------------------------------------------------------
# T14: RSS / runtime 计量 helper
# ---------------------------------------------------------------------------


def _rss_mb_self() -> float:
    """Return this process' peak RSS (MB). Best-effort cross-platform."""
    # tracemalloc 只能看 Python 堆；RSS 优先用 Unix resource 再 Windows psutil。
    rss_bytes: int | None = None
    if _resource is not None:
        try:
            # Unix: ru_maxrss KB on Linux, bytes on macOS — heuristic区分
            ru = _resource.getrusage(_resource.RUSAGE_SELF)
            raw = ru.ru_maxrss
            rss_bytes = raw if raw / 1024 > 8 * 1024 * 1024 else raw * 1024
        except (AttributeError, NameError):
            pass
    if rss_bytes is None:
        # Windows / 其他: 尝试 psutil
        try:
            import psutil  # type: ignore

            rss_bytes = psutil.Process().memory_info().rss
        except Exception:  # noqa: BLE001
            rss_bytes = 0
    return round(rss_bytes / (1024 * 1024), 2)


def _run_stage_capture(
    index: int, total: int, label: str, script_name: str
) -> dict[str, Any]:
    """Run one benchmark script; returns a JSON-able report stanza."""
    print(f"\n[{index}/{total}] {label}", flush=True)
    script_path = os.path.join(BENCHMARK_DIR, script_name)
    stanza: dict[str, Any] = {
        "index": index,
        "label": label,
        "script": script_name,
        "script_path": script_path,
        "exists": os.path.isfile(script_path),
        "success": False,
        "exit_code": None,
        "duration_seconds": None,
        "peak_rss_mb_runner": None,  # runner 进程在子进程结束后的当前 RSS
    }
    if not stanza["exists"]:
        print(f"  ✗ missing script: {script_path}", flush=True)
        return stanza

    t0 = time.perf_counter()
    sys.stdout.flush()
    proc = subprocess.run(
        [PYTHON, script_path],
        cwd=REPO_ROOT,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    dt = round(time.perf_counter() - t0, 3)
    stanza["exit_code"] = proc.returncode
    stanza["duration_seconds"] = dt
    stanza["peak_rss_mb_runner"] = _rss_mb_self()

    if proc.returncode != 0:
        print(f"  ✗ failed (exit {proc.returncode}) in {dt:.2f}s", flush=True)
        return stanza

    stanza["success"] = True
    print(
        f"  ✓ completed in {dt:.2f}s (runner RSS ~{stanza['peak_rss_mb_runner']} MB)",
        flush=True,
    )
    return stanza


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--report-json",
        metavar="FILE",
        default=None,
        help="Write a structured JSON report (per-stage duration/rss + summary) to FILE.",
    )
    args = ap.parse_args()

    total = len(STAGES)
    print("=" * 32, flush=True)
    print(" LoRa Benchmark Suite", flush=True)
    print("=" * 32, flush=True)

    tracemalloc.start()
    overall_t0 = time.perf_counter()
    stages: list[dict[str, Any]] = []
    all_ok = True
    for i, (label, script) in enumerate(STAGES, start=1):
        s = _run_stage_capture(i, total, label, script)
        stages.append(s)
        if not s["success"]:
            all_ok = False
            break  # stop on first failure

    overall_dt = round(time.perf_counter() - overall_t0, 3)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    pyheap_peak_mb = round(peak / (1024 * 1024), 2)

    print(flush=True)
    if all_ok:
        print("All benchmarks finished.", flush=True)
    else:
        print("Benchmark suite halted (see errors above).", flush=True)

    print(flush=True)
    print("Results:", flush=True)
    print("docs/benchmark/", flush=True)
    figure_files: list[str] = []
    if os.path.isdir(RESULTS_DIR):
        for name in sorted(os.listdir(RESULTS_DIR)):
            full = os.path.join(RESULTS_DIR, name)
            kind = "d" if os.path.isdir(full) else "f"
            print(f"  [{kind}] {name}", flush=True)
            if kind == "f":
                figure_files.append(name)
            else:
                for root, _, files in os.walk(full):
                    for fn in files:
                        figure_files.append(
                            os.path.relpath(os.path.join(root, fn), REPO_ROOT)
                        )

    report: dict[str, Any] | None = None
    if args.report_json:
        passed = sum(1 for s in stages if s["success"])
        report = {
            "runner": "scripts/run_all_benchmarks.py",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "python": sys.version,
            "platform": sys.platform,
            "summary": {
                "stages_total": total,
                "stages_passed": passed,
                "all_passed": bool(all_ok),
                "duration_seconds_total": overall_dt,
                "python_heap_peak_mb": pyheap_peak_mb,
                "runner_peak_rss_mb_after_last_stage": stages[-1]["peak_rss_mb_runner"]
                if stages
                else None,
            },
            "outputs_dir": os.path.relpath(RESULTS_DIR, REPO_ROOT),
            "outputs": figure_files,
            "stages": stages,
        }
        report_path = args.report_json
        if not os.path.isabs(report_path):
            report_path = os.path.join(REPO_ROOT, report_path)
        os.makedirs(os.path.dirname(os.path.abspath(report_path)) or ".", exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(flush=True)
        print(f"Benchmark JSON report -> {report_path}", flush=True)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
