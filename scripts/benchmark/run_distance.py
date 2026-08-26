"""Benchmark 3 — Distance vs PDR (Step 4, distance curve).

Read-only usage of the frozen simulator stack through backend.engine.
We need a node at a *precise* distance from a *single* gateway, which the
frozen SimulationEngine.configure() cannot express (it only randomly scatters
nodes). So we add a tiny outer-layer subclass that overrides _build_topology()
to place one gateway at the origin and one node at (distance, 0).

This does NOT modify simulator/ gateway/ backend/ source — the override lives
entirely in this script (scripts/benchmark/).

Fixed: nodes=1, gateway=1, ADR=OFF, SF=7.
Swept: distance = 100..5000 m.

Because the channel has log-normal shadow fading (sigma=4 dB) and the node
retries up to MAX_RETRY times, a single deterministic run would show a near
vertical cliff. To obtain a statistically meaningful link-budget *curve* we
average PDR over N_SEEDS independent shadow-fading realizations per distance
(seeding the global RNG so each seed is reproducible and distinct).

Outputs: docs/benchmark/distance.csv and
docs/benchmark/figures/distance_pdr.png.
"""

import os
import random
import statistics
import sys

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Make the project root importable so `from common import ...` and the backend
# imports resolve when executed as a script inside scripts/benchmark/.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from common import BenchmarkEngine  # noqa: E402

from gateway.gateway import Gateway  # noqa: E402 noqa
from simulator.node import SensorNode  # noqa: E402

DISTANCES = [100, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000]
NODE_COUNT = 1
GATEWAY_COUNT = 1
SEED_BASE = 42
N_SEEDS = 30
DURATION = 100.0  # one scheduled transmission (+ retransmissions)


class DistanceBenchmarkEngine(BenchmarkEngine):
    """Places a single gateway at (0,0) and a single node at (distance, 0).

    Overrides only _build_topology(); all frozen behaviour is inherited.
    """

    def __init__(self, distance=1000.0, **kwargs):
        # Set the target BEFORE super().__init__() so the implicit initial
        # _build() (which calls _build_topology) sees it.
        self.target_distance = float(distance)
        super().__init__(**kwargs)

    def _build_topology(self):
        gateway = Gateway("GW001", 0.0, 0.0)
        node = SensorNode("Node001", self.target_distance, 0.0)
        return [node], [gateway]


def run_one(distance, seed, adr_enabled=False):
    """Run a single (distance, seed, adr) trial; return delivered PDR (0..1)."""
    # Seed the global RNG so the shadow-fading realization is reproducible
    # and distinct per seed (propagation.py draws shadow from global random).
    random.seed(seed)
    engine = DistanceBenchmarkEngine(distance=distance)
    engine.configure(
        node_count=NODE_COUNT,
        adr_enabled=adr_enabled,  # False -> SF pinned at DEFAULT_SF=7
        seed=seed,
        duration=DURATION,
    )
    engine.start()
    while not engine.finished():
        engine.step()
    stats = engine.get_statistics()
    return stats.get("pdr", 0.0)


def sweep(adr_enabled):
    label = "ADR ON" if adr_enabled else "ADR OFF"
    rows = []
    for d in DISTANCES:
        pdrs = [run_one(d, SEED_BASE + s, adr_enabled) for s in range(N_SEEDS)]
        mean_pdr = statistics.mean(pdrs)
        std_pdr = statistics.pstdev(pdrs) if len(pdrs) > 1 else 0.0
        rows.append(
            {
                "distance_m": d,
                "adr": label,
                "pdr_mean": round(mean_pdr, 4),
                "pdr_std": round(std_pdr, 4),
                "pdr_min": round(min(pdrs), 4),
                "pdr_max": round(max(pdrs), 4),
            }
        )
        print(
            f"[{label}] distance={d:5d}m  meanPDR={mean_pdr:.3f}  "
            f"std={std_pdr:.3f}  [min={min(pdrs):.2f}, max={max(pdrs):.2f}]"
        )
    return rows


def main():
    rows = sweep(adr_enabled=False) + sweep(adr_enabled=True)
    df = pd.DataFrame(rows)
    print("\n" + df.to_string(index=False))

    out_csv = "docs/benchmark/distance.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nSaved {out_csv}")

    # ---- Link-budget curve (ADR OFF vs ADR ON) ----
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = {"ADR OFF": "#d62728", "ADR ON": "#2ca02c"}
    for adr in ("ADR OFF", "ADR ON"):
        sub = df[df.adr == adr]
        ax.plot(
            sub.distance_m,
            sub.pdr_mean,
            marker="o",
            color=colors[adr],
            linewidth=2,
            label=f"Mean PDR ({adr})",
        )
        ax.fill_between(
            sub.distance_m,
            (sub.pdr_mean - sub.pdr_std).clip(lower=0),
            (sub.pdr_mean + sub.pdr_std).clip(upper=1),
            color=colors[adr],
            alpha=0.15,
        )
    ax.axhline(1.0, ls="--", color="gray", alpha=0.5)
    ax.axhline(0.0, ls="--", color="gray", alpha=0.5)
    ax.set_xlabel("Distance from gateway (m)")
    ax.set_ylabel("Packet Delivery Ratio (PDR)")
    ax.set_title(
        "Benchmark 3 — LoRa Link Reliability vs Distance\n"
        "(1 node, 1 gateway, SF7 baseline, TX=14 dBm)"
    )
    ax.set_ylim(-0.05, 1.1)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")

    out_png = "docs/benchmark/figures/distance_pdr.png"
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    print(f"Saved {out_png}")


if __name__ == "__main__":
    main()
