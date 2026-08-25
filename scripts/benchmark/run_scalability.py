"""Benchmark 1 — Node Scalability (Step 2.5 smoke test).

Runs the scalability sweep and writes docs/benchmark/scalability.csv plus
docs/benchmark/figures/scalability.png.

For this first smoke test only 10 / 50 / 100 nodes are run (per Step 2.5);
200 and 500 are enabled in later steps.
"""
from common import run_experiment
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


nodes = [
    10,
    50,
    100,
    200,
    500,
]


results = []


for n in nodes:

    print(
        f"Running {n} nodes..."
    )

    result = run_experiment(
        node_count=n
    )

    results.append(result)


df = pd.DataFrame(results)


print(df)


df.to_csv(
    "docs/benchmark/scalability.csv",
    index=False
)


plt.figure()

plt.plot(
    df["nodes"],
    df["pdr"],
    marker="o"
)

plt.xlabel(
    "Number of Nodes"
)

plt.ylabel(
    "PDR"
)

plt.title(
    "LoRa Scalability: Nodes vs PDR"
)


plt.savefig(
    "docs/benchmark/figures/scalability.png"
)

print(
    "Saved scalability.png"
)
