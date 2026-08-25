"""LoRa 网关（Sprint 3 实现）。

职责：接收数据包、碰撞检测、RSSI 计算、MQTT 转发。
TODO(Sprint 3): Gateway.receive / forward / publish_mqtt。
"""
from simulator.packet import Packet


class Gateway:
    def __init__(self, gateway_id, x, y, coverage=3000.0):
        self.gateway_id = gateway_id
        self.x = x
        self.y = y
        self.coverage = coverage            # 覆盖半径（米）
        self.received_packets: list[Packet] = []

    def receive(self, packet: Packet):
        raise NotImplementedError("Sprint 3: receive()")
