"""
LoRa channel link test
"""

from simulator.packet import Packet
from simulator.channel import LoRaChannel


class MockGateway:
    def __init__(self):
        self.id = "GW001"
        self.x = 1000
        self.y = 1000


def test_channel():
    packet = Packet(
        node_id="Node001",
        payload={"temperature": 25.5},
        sf=7,
        tx_power=14,
    )

    # 模拟节点位置
    packet.x = 1500
    packet.y = 1200

    gateway = MockGateway()
    channel = LoRaChannel()

    result = channel.calculate_link(packet, gateway)

    print("===== LoRa Channel Test =====")
    print(f"Node: {result.node_id}")
    print(f"Distance: {result.distance} m")
    print(f"RSSI: {result.rssi} dBm")
    print(f"SNR: {result.snr} dB")
    print(f"SF: {result.sf}")
    print(f"SUCCESS: {result.success}")

    # 确定性断言：距离为几何计算，与 shadow fading 无关；
    # SF7 灵敏度 -123，中央网关 ~538m 处 RSSI 远高于阈值，链路稳定成功。
    assert result.node_id == "Node001"
    assert abs(result.distance - 538.52) < 0.1
    assert result.success is True


if __name__ == "__main__":
    test_channel()
