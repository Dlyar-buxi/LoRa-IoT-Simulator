"""
LoRa network simulation integration test
"""

import random

from simulator.config import (
    NODE_COUNT,
    AREA_SIZE,
    SEED,
)

from simulator.node import SensorNode
from gateway.gateway import Gateway
from simulator.simulation import Simulation


# 固定随机种子，保证可复现
random.seed(SEED)

nodes = [
    SensorNode(
        f"Node{i + 1:03}",
        random.uniform(0, AREA_SIZE),
        random.uniform(0, AREA_SIZE),
    )
    for i in range(NODE_COUNT)
]

# 2 个网关，对称覆盖农场
gateways = [
    Gateway("GW1", 500, 500),
    Gateway("GW2", 1500, 1500),
]

sim = Simulation(nodes, gateways, duration=60.0)
sim.run()

stats = sim.statistics()

print("===== LoRa Simulation Test =====")
print()
print("Simulation time:")
print(f"{int(sim.duration)}s")
print()
print("Nodes:")
print(f"{len(nodes)}")
print()
print("Generated packets:")
print(f"{stats['generated']}")
print()
print("Received packets:")
print(f"{stats['received']}")
print()
print("Lost packets:")
print(f"{stats['lost']}")
print()
print("PDR:")
print(f"{stats['pdr']:.1f}%")
print()
print("Throughput:")
print(f"{stats['throughput']:.2f} packets/s")
print()
print("Simulation PASS")
