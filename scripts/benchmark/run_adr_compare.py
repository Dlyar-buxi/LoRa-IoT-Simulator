"""Benchmark 2 — ADR ON vs OFF comparison (Step 3).

Read-only usage of the frozen simulator stack through backend.engine.
We sweep the physical deployment scale (area_size) to create a link-budget
stress gradient, and at each scale compare ADR enabled vs disabled.

Why stress with area_size?
  In the default frozen topology (2 GWs at (500,500)/(1500,1500), TX=14 dBm,
  path-loss n=3) every node already clears the SF7 sensitivity floor even at
  the worst corner (~1581 m -> rssi ~ -113 dBm >> SF7 -123 dBm). So at the
  nominal 2000 m scale ADR is inert (it can only try to *lower* SF from 7,
  which is clamped). Enlarging the deployment area pushes nodes beyond the
  SF7 sensitivity threshold, where LoRa's per-SF processing gain
  (SF_SENSITIVITY: SF7=-123 .. SF12=-137 dBm) lets ADR rescue weak links by
  elevating SF. This isolates the ADR effect while holding the random geometry
  constant: Average RSSI must be identical between ON and OFF (control check).

Metrics: PDR, Packet Loss (1-PDR), Average SF, Average RSSI, throughput,
collision rate. Outputs docs/benchmark/adr_compare.csv and
docs/benchmark/figures/adr_compare.png (2x2 paper-quality panels).

Does NOT modify any simulator/ gateway/ backend/ source.
"""
import os
import statistics
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Make the project root importable so `from common import ...` and the backend
# imports resolve when executed as a script inside scripts/benchmark/.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common import BenchmarkEngine  # noqa: E402


# Sweep over deployment scale. 2000 m is the inert baseline; 3000-4000 m show
# the ADR SF-adaptation onset; 5000-8000 m show the full PDR rescue gap.
AREAS = [2000, 3000, 4000, 5000, 6500, 8000]
NODE_COUNT = 200
SEED = 42


def run_case(area_size, adr_enabled):
    """Run one (area, ADR) experiment and aggregate the required metrics."""
    e = BenchmarkEngine()
    e.configure(
        node_count=NODE_COUNT,
        area_size=area_size,
        adr_enabled=adr_enabled,
        seed=SEED,
    )
    e.start()
    while not e.finished():
        e.step()

    stats = e.get_statistics()
    packets = e.get_packets()

    rssis, sfs, success, failed = [], [], 0, 0
    for p in packets:
        if "rssi" in p:
            rssis.append(p["rssi"])
        if "sf" in p:
            sfs.append(p["sf"])
        if p.get("success"):
            success += 1
        else:
            failed += 1

    pdr = stats.get("pdr", 0.0)
    return {
        "area_size": area_size,
        "adr": "ON" if adr_enabled else "OFF",
        "pdr": round(pdr, 4),
        "packet_loss": round(1.0 - pdr, 4),
        "avg_sf": round(statistics.mean(sfs), 3) if sfs else None,
        "avg_rssi": round(statistics.mean(rssis), 3) if rssis else None,
        "throughput": round(stats.get("throughput", 0.0), 4),
        "collision_rate": round(
            failed / (success + failed), 4) if (success + failed) else 0.0,
    }


def main():
    rows = []
    for area in AREAS:
        for adr in (False, True):
            print(f"Running area={area:5d} ADR={'ON' if adr else 'OFF'}...")
            rows.append(run_case(area, adr))

    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False))

    out_csv = "docs/benchmark/adr_compare.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    # ---- 2x2 paper-quality figure ----
    colors = {"ON": "#1f77b4", "OFF": "#d62728"}
    linestyles = {"ON": "-", "OFF": "--"}
    markers = {"ON": "o", "OFF": "s"}

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    # Panel 1: PDR
    for adr in ("ON", "OFF"):
        sub = df[df.adr == adr]
        axes[0, 0].plot(sub.area_size, sub.pdr, marker=markers[adr],
                        color=colors[adr], linestyle=linestyles[adr],
                        label=f"ADR {adr}")
    axes[0, 0].set_title("PDR vs Deployment Area")
    axes[0, 0].set_xlabel("Area size (m, square side)")
    axes[0, 0].set_ylabel("Packet Delivery Ratio")
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # Panel 2: Packet Loss
    for adr in ("ON", "OFF"):
        sub = df[df.adr == adr]
        axes[0, 1].plot(sub.area_size, sub.packet_loss, marker=markers[adr],
                        color=colors[adr], linestyle=linestyles[adr],
                        label=f"ADR {adr}")
    axes[0, 1].set_title("Packet Loss vs Deployment Area")
    axes[0, 1].set_xlabel("Area size (m, square side)")
    axes[0, 1].set_ylabel("Packet Loss (1 - PDR)")
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # Panel 3: Average SF (the ADR adaptation mechanism)
    for adr in ("ON", "OFF"):
        sub = df[df.adr == adr]
        axes[1, 0].plot(sub.area_size, sub.avg_sf, marker=markers[adr],
                        color=colors[adr], linestyle=linestyles[adr],
                        label=f"ADR {adr}")
    axes[1, 0].set_title("Average SF vs Deployment Area")
    axes[1, 0].set_xlabel("Area size (m, square side)")
    axes[1, 0].set_ylabel("Average Spreading Factor")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # Panel 4: Average RSSI (control - must overlap: geometry is invariant)
    for adr in ("ON", "OFF"):
        sub = df[df.adr == adr]
        axes[1, 1].plot(sub.area_size, sub.avg_rssi, marker=markers[adr],
                        color=colors[adr], linestyle=linestyles[adr],
                        label=f"ADR {adr}")
    axes[1, 1].set_title("Average RSSI vs Deployment Area (control)")
    axes[1, 1].set_xlabel("Area size (m, square side)")
    axes[1, 1].set_ylabel("Average RSSI (dBm)")
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    fig.suptitle("Benchmark 2 — ADR ON/OFF under Link-Budget Stress",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out_png = "docs/benchmark/figures/adr_compare.png"
    fig.savefig(out_png, dpi=130)
    print(f"Saved {out_png}")


if __name__ == "__main__":
    main()
