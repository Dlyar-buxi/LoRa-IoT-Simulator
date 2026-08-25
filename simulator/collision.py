"""
LoRa Collision Detector

Sprint 3.3

职责：判断两个 LoRa 数据包是否发生碰撞。

判定（严格按 LoRa 物理特性）：
1. 同频率（不同信道不冲突）
2. 同扩频因子 SF（不同 SF 可同时解调）
3. 时间重叠（发送时段相交）
4. RSSI 捕获效应：两信号强度差 < 阈值时才互相干扰

不负责：RSSI 计算 / airtime 计算 / MAC 重传 / Gateway 接收
（属于 channel.py / mac.py / gateway.py）
"""

from simulator.config import COLLISION_SNR_THRESHOLD


class CollisionDetector:
    def check_collision(self, packet1, packet2):
        """返回 True 表示两个包发生碰撞（互相破坏）。"""
        if not self.same_frequency(packet1, packet2):
            return False
        if not self.same_spreading_factor(packet1, packet2):
            return False
        if not self.overlap_time(packet1, packet2):
            return False
        return self.rssi_collision(packet1, packet2)

    def same_frequency(self, packet1, packet2):
        return packet1.frequency == packet2.frequency

    def same_spreading_factor(self, packet1, packet2):
        return packet1.sf == packet2.sf

    def overlap_time(self, packet1, packet2):
        return (
            packet1.tx_start_time < packet2.tx_end_time
            and packet2.tx_start_time < packet1.tx_end_time
        )

    def rssi_collision(self, packet1, packet2):
        return abs(packet1.rssi - packet2.rssi) < COLLISION_SNR_THRESHOLD
