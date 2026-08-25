"""
Gateway multi-node test
"""

from simulator.node import SensorNode
from simulator.channel import LoRaChannel
from gateway.gateway import Gateway

import random


def test_gateway_network():
    # 固定随机种子，保证可复现
    random.seed(42)

    NODE_COUNT = 200

    gateway = Gateway("GW001", 1000, 1000)
    channel = LoRaChannel()

    print("===== LoRa Gateway Network Test =====")

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

    assert stats["total"] == NODE_COUNT
    assert stats["received"] == NODE_COUNT


if __name__ == "__main__":
    test_gateway_network()
