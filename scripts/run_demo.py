#!/usr/bin/env python3
"""
LoRa-IoT-Simulator local automated demo.

Runs a short headless experiment and exports
a Markdown report.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(cmd):
    print("\n==>", " ".join(cmd))

    result = subprocess.run(
        cmd,
        cwd=ROOT
    )

    if result.returncode != 0:
        raise SystemExit(
            f"Command failed: {' '.join(cmd)}"
        )


def main():
    python = sys.executable

    print("=" * 40)
    print(" LoRa IoT Simulator Demo")
    print("=" * 40)

    print("\n[1/2] Generate experiment")

    run([
        python,
        "scripts/generate_experiment.py",
        "--nodes",
        "20",
        "--area",
        "400",
        "--seed",
        "1",
        "--duration",
        "60",
        "--gateways",
        "2",
        "--db",
        "demo.db",
    ])

    print("\n[2/2] Export report")

    run([
        python,
        "scripts/export_report.py",
        "--db",
        "demo.db",
        "--out",
        "demo_report.md",
    ])

    print("\nDone.")
    print("Artifacts:")
    print("  - demo.db")
    print("  - demo_report.md")


if __name__ == "__main__":
    main()
