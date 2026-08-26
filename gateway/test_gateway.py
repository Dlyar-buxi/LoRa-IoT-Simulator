"""
Gateway multi-node test
"""

from simulator.node import SensorNode
from simulator.channel_model import ShadowingChannel, ChannelModelLinkAdapter
from simulator import config
from gateway.gateway import Gateway

import random


def test_gateway_network():
    # 固定随机种子, 保证节点布放可复现 (channel 使用自身私有 seed, 见下)
    random.seed(42)

    NODE_COUNT = 200

    gateway = Gateway("GW001", 1000, 1000)
    # 等价于 legacy LoRaChannel (LogDistance n=3.0 + 高斯阴影 σ=4),
    # 经 ADR-001 adapter 接入 (见 docs/design/legacy-channel-migration.md §8 Option A)。
    channel = ChannelModelLinkAdapter(
        ShadowingChannel(
            sigma=config.SHADOW_SIGMA,
            seed=config.SEED,
        )
    )

    print("===== LoRa Gateway Network Test (ChannelModel) =====")

    for i in range(NODE_COUNT):
        node = SensorNode(
            f"Node{i+1:03}",
            random.randint(0, 2000),
            random.randint(0, 2000),
        )

        packet = node.create_packet()

        # 注入节点位置
        packet.x = node.x
        packet.y = node.y

        packet = channel.calculate_link(packet, gateway)

        gateway.receive(packet)

    print()

    stats = gateway.statistics()
    print(stats)

    # 统计型断言: 新模型 success = random() < pdr (概率采样),
    # 不再等价于 legacy 硬阈值 rssi >= sensitivity; 故改为接收率 >= 95%。
    assert stats["total"] == NODE_COUNT
    assert stats["received"] >= int(NODE_COUNT * 0.95)


if __name__ == "__main__":
    test_gateway_network()
