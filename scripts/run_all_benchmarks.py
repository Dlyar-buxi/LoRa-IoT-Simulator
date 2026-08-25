#!/usr/bin/env python3
"""Sprint 6.2.1 — Unified LoRa Benchmark Suite runner.

Orchestrates the three Sprint 6.1 experiments end-to-end and aggregates
their outputs under ``docs/benchmark/``.  This is a thin outer-layer
wrapper only: it does NOT import or modify the frozen core
(``simulator/``, ``gateway/``, ``backend/``) and it does NOT refactor the
existing per-benchmark scripts — it simply runs each one via subprocess
with the repository root as the working directory so their relative
output paths (``docs/benchmark/...``) resolve correctly.

Usage (from anywhere inside the repo):
    python scripts/run_all_benchmarks.py
"""
import os
import subprocess
import sys

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


def run_stage(index, total, label, script_name):
    """Run one benchmark script; return True on success (exit 0)."""
    # flush=True keeps the section markers interleaved with the child's
    # own output even when stdout is a pipe (non-TTY buffering).
    print(f"\n[{index}/{total}] {label}", flush=True)
    script_path = os.path.join(BENCHMARK_DIR, script_name)
    if not os.path.isfile(script_path):
        print(f"  ✗ missing script: {script_path}", flush=True)
        return False

    sys.stdout.flush()
    proc = subprocess.run(
        [PYTHON, script_path],
        cwd=REPO_ROOT,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    if proc.returncode != 0:
        print(f"  ✗ failed (exit {proc.returncode})", flush=True)
        return False

    print("  ✓ completed", flush=True)
    return True


def main():
    total = len(STAGES)
    print("=" * 32, flush=True)
    print(" LoRa Benchmark Suite", flush=True)
    print("=" * 32, flush=True)

    all_ok = True
    for i, (label, script) in enumerate(STAGES, start=1):
        if not run_stage(i, total, label, script):
            all_ok = False
            break  # stop on first failure so partial results stay visible

    print(flush=True)
    if all_ok:
        print("All benchmarks finished.", flush=True)
    else:
        print("Benchmark suite halted (see errors above).", flush=True)

    print(flush=True)
    print("Results:", flush=True)
    print("docs/benchmark/", flush=True)
    if os.path.isdir(RESULTS_DIR):
        for name in sorted(os.listdir(RESULTS_DIR)):
            print(f"  {name}", flush=True)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
