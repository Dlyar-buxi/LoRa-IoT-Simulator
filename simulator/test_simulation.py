"""
LoRa network simulation integration test

注意: 本测试是「Channel Model 集成冒烟测试」, 验证
ChannelModelLinkAdapter + LogDistanceChannel 能端到端驱动仿真
(节点 -> 网关选择 -> 信道评估 -> 统计)。

⚠️ 它不是性能指标基准: v0.1 无阴影衰落 / 瑞利 / collision 耦合,
默认场景下 PDR 会饱和在 ~100%, 这只能说明适配器工作, 不代表信道质量好。
解读 PDR 时务必结合 v0.1 的能力边界, 见 docs/design/channel-model-api.md。
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


def test_simulation_channel_integration():
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

    assert stats["generated"] == NODE_COUNT
    assert 0.0 <= stats["pdr"] <= 100.0
    assert stats["received"] <= stats["generated"]


if __name__ == "__main__":
    test_simulation_channel_integration()
