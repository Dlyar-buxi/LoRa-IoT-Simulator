#!/usr/bin/env python3
"""Export a stored experiment to Markdown.

Reads the SQLite database written by `generate_experiment.py` (or by the
running backend) and prints a human-readable report for the chosen experiment.
Imports only `backend.database`; never starts the web server.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import ExperimentRecorder  # noqa: E402


def fmt_pct(x):
    return f"{x * 100:.1f}%" if isinstance(x, (int, float)) else "n/a"


def run(args):
    db_path = args.db or os.getenv("DB_PATH", "experiments.db")
    rec = ExperimentRecorder(db_path=db_path, enabled=True)
    if not rec.connect():
        print(f"ERROR: cannot open {db_path}")
        return 2

    exps = rec.list_experiments()
    if not exps:
        print(f"No experiments found in {db_path}")
        rec.close()
        return 1

    target = args.id or exps[0]["id"]  # latest by default
    exp = rec.get_experiment(target)
    if exp is None:
        print(f"Experiment {target} not found")
        rec.close()
        return 1

    stats = exp.get("statistics") or {}
    lines = []
    lines.append(f"# Experiment {exp['id']} Report")
    lines.append("")
    lines.append(f"- **Created:** {exp.get('created_at')}")
    lines.append(f"- **Seed:** {exp.get('seed')}")
    lines.append(f"- **Nodes:** {exp.get('node_count')}")
    lines.append(f"- **Area:** {exp.get('area_size')} m")
    lines.append(f"- **Duration:** {exp.get('duration')} s")
    lines.append(f"- **ADR enabled:** {exp.get('adr_enabled')}")
    lines.append(f"- **Finalized:** {exp.get('finalized')}")
    lines.append("")
    lines.append("## Network performance")
    lines.append("")
    lines.append(f"- **PDR (Packet Delivery Ratio):** {fmt_pct(stats.get('pdr'))}")
    lines.append(f"- **Throughput:** {stats.get('throughput')}")
    lines.append(f"- **Retransmissions:** {stats.get('retransmissions')}")
    lines.append(
        f"- **Packet Loss Rate (1 - PDR):** {fmt_pct(1 - stats.get('pdr', 0))}"
    )
    lines.append("")
    lines.append("## Gateways")
    lines.append("")
    lines.append("| Gateway | Received | Avg RSSI | X | Y |")
    lines.append("| --- | --- | --- | --- | --- |")
    for g in exp.get("gateways") or []:
        avg = g.get("avg_rssi")
        lines.append(
            f"| {g.get('id')} | {g.get('received')} | "
            f"{avg if avg is not None else 'n/a'} | {g.get('x')} | {g.get('y')} |"
        )
    lines.append("")
    lines.append("## Nodes (sample)")
    lines.append("")
    lines.append("| Node | SF | Gateway | RSSI | SNR | Battery | Online |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    nodes = exp.get("nodes") or []
    for n in nodes[: args.top]:
        lines.append(
            f"| {n.get('id')} | {n.get('sf')} | {n.get('gateway')} | "
            f"{n.get('rssi')} | {n.get('snr')} | {n.get('battery')} | {n.get('online')} |"
        )
    if len(nodes) > args.top:
        lines.append("")
        lines.append(f"_... and {len(nodes) - args.top} more nodes._")

    text = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Report written to {args.out}")
    else:
        print(text)

    rec.close()
    return 0


def main():
    p = argparse.ArgumentParser(description="Export an experiment to Markdown.")
    p.add_argument(
        "--db",
        type=str,
        default=None,
        help="SQLite path (default: $DB_PATH or experiments.db)",
    )
    p.add_argument(
        "--id", type=int, default=None, help="Experiment id (default: latest)"
    )
    p.add_argument(
        "--out", type=str, default=None, help="Output .md path (default: stdout)"
    )
    p.add_argument("--top", type=int, default=20, help="Max nodes to list")
    args = p.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
