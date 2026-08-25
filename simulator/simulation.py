"""
LoRa Network Simulation (orchestration)

Sprint 3.4

职责：把已有模块编排成一次完整网络仿真。
- SensorNode 生成数据包
- Scheduler 按时间触发发送事件（离散事件仿真）
- LoRaChannel 计算 RSSI/SNR/成功
- CollisionDetector 检测同信道冲突
- Gateway 接收并统计

不修改任何底层模块，只做编排。
"""

import math
import random

from simulator import config
from simulator.scheduler import Scheduler
from simulator.channel import LoRaChannel
from simulator.collision import CollisionDetector
from simulator.node import SensorNode


class Simulation:
    def __init__(self, nodes, gateways, duration):
        self.nodes = nodes
        self.gateways = gateways
        self.duration = duration

        self.scheduler = Scheduler()
        self.channel = LoRaChannel()
        self.collision_detector = CollisionDetector()
        self.active_packets = []

        self.generated = 0
        self.received = 0
        self.lost = 0

        self._rng = random.Random(config.SEED)
        self._schedule_transmissions()

    def _schedule_transmissions(self):
        """为每个节点在 [0, duration] 内随机安排一次发送事件。"""
        for node in self.nodes:
            t = self._rng.uniform(0.0, self.duration)
            # lambda 用默认参数捕获当前 node，避免闭包变量后期绑定问题
            self.scheduler.add_event(
                t,
                node.node_id,
                "TRANSMIT",
                lambda ev, n=node: self._on_transmit(ev, n),
            )

    def _on_transmit(self, event, node):
        """发送事件回调：生成包 -> 信道 -> 碰撞 -> 网关。"""
        packet = node.create_packet()

        # 时间字段（注意与 timestamp 区分：
        # timestamp=数据生成时间，tx_start=占用信道开始）
        packet.tx_start_time = self.scheduler.current_time
        # airtime 由 SF 推算（create_packet 默认 0，这里补算，
        # 否则时间窗口为 0，永远不重叠，碰撞检测失效）
        packet.airtime = config.sf_to_time_on_air(packet.sf)
        packet.tx_end_time = packet.tx_start_time + packet.airtime

        # 选最近网关做链路计算
        nearest = min(
            self.gateways,
            key=lambda g: math.hypot(packet.x - g.x, packet.y - g.y),
        )
        self.channel.calculate_link(packet, nearest)

        # 碰撞检测：与当前仍在空中的包逐一比对
        self.active_packets = [
            p for p in self.active_packets
            if p.tx_end_time > self.scheduler.current_time
        ]
        collided = False
        for p in self.active_packets:
            if self.collision_detector.check_collision(packet, p):
                collided = True
                break

        # 最终成功 = 信道成功 且 未碰撞
        packet.success = packet.success and not collided

        nearest.receive(packet)
        self.active_packets.append(packet)

        self.generated += 1
        if packet.success:
            self.received += 1
        else:
            self.lost += 1

    def run(self):
        """运行离散事件主循环。"""
        self.scheduler.run()

    def statistics(self):
        generated = self.generated
        received = self.received
        lost = self.lost
        pdr = (received / generated * 100.0) if generated else 0.0
        throughput = (received / self.duration) if self.duration else 0.0
        return {
            "generated": generated,
            "received": received,
            "lost": lost,
            "pdr": pdr,
            "throughput": throughput,
        }
