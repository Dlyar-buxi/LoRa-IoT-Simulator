"""
LoRa Network Simulation (orchestration)

Sprint 3.4: 把已有模块编排成一次完整网络仿真。
Sprint 4.1: 通过节点的 LoRaMAC 驱动重传状态机，
            失败时随机退避后重排 RETRANSMIT 事件，最多 MAX_RETRY 次；
            统计口径改为「唯一业务包」（方案 A）。

不修改任何底层模块，只做编排。
"""

import random

from simulator import config
from simulator.scheduler import Scheduler
from simulator.channel_model import ChannelModelLinkAdapter, LogDistanceChannel
from simulator.collision import CollisionDetector
from simulator.node import SensorNode
from simulator.mac import LoRaMAC, MacState
from simulator.adr import adapt_sf
from simulator.gateway_selector import select_best_gateway


class Simulation:
    def __init__(self, nodes, gateways, duration):
        self.nodes = nodes
        self.gateways = gateways
        self.duration = duration

        self.scheduler = Scheduler()
        # Channel Model v0.1: 用适配器把新 ChannelModel 接入既有调用点
        self.channel = ChannelModelLinkAdapter(
            LogDistanceChannel(
                path_loss_exponent=config.PATH_LOSS_EXPONENT,
                noise_floor=config.NOISE_FLOOR,
                frequency=config.FREQUENCY,
            ),
            environment=config.ENVIRONMENT,
        )
        self.collision_detector = CollisionDetector()
        self.active_packets = []

        # 每个节点一个 MAC 实例（Sprint 4.1 驱动重传状态机）
        self.macs = {node.node_id: LoRaMAC(node) for node in nodes}

        # 统计（方案 A：以唯一业务包为口径）
        self.generated = 0        # 唯一下行包数量（= 调度时每节点 1 个）
        self.received = 0        # 最终成功送达数量
        self.lost = 0            # 超过最大重试次数仍失败数量
        self.retransmissions = 0 # 所有额外发送次数

        self._rng = random.Random(config.SEED)
        self._schedule_transmissions()

    def _schedule_transmissions(self):
        """为每个节点在 [0, duration] 内随机安排一次发送事件。"""
        for node in self.nodes:
            self.generated += 1  # 唯一业务包计数
            t = self._rng.uniform(0.0, self.duration)
            # lambda 用默认参数捕获当前 node，避免闭包变量后期绑定问题
            self.scheduler.add_event(
                t,
                node.node_id,
                "TRANSMIT",
                lambda ev, n=node: self._on_transmit(ev, n),
            )

    def _on_transmit(self, event, node):
        """发送事件回调：生成包 -> 信道 -> 碰撞 -> 网关 -> 失败则重传。

        Sprint 4.1：通过节点的 LoRaMAC 驱动状态机，
        失败时随机退避后重排 RETRANSMIT 事件，最多重试 MAX_RETRY 次。
        """
        mac = self.macs[node.node_id]

        # 区分首次发送 / 重传（退避结束）
        if mac.state == MacState.WAIT_BACKOFF:
            mac.retry_transmission()       # WAIT_BACKOFF -> TRANSMITTING
            self.retransmissions += 1
        else:
            mac.start_transmission()       # IDLE -> TRANSMITTING

        packet = node.create_packet()
        # 遥测：本包这是第几次发送（0=首次，1=第 1 次重传...）
        packet.retry_count = mac.retry_count

        # 时间字段（注意与 timestamp 区分：
        # timestamp=数据生成时间，tx_start=占用信道开始）
        packet.tx_start_time = self.scheduler.current_time
        # airtime 由 SF 推算（create_packet 默认 0，这里补算，
        # 否则时间窗口为 0，永远不重叠，碰撞检测失效）
        packet.airtime = config.sf_to_time_on_air(packet.sf)
        packet.tx_end_time = packet.tx_start_time + packet.airtime

        # 多网关选择（Sprint 4.3）：按上行 RSSI 选最佳网关
        best = select_best_gateway(node, self.gateways, self.channel)
        node.selected_gateway = best.id
        nearest = best

        self.channel.calculate_link(packet, nearest)

        # ADR 反馈（Sprint 4.2）：把上行链路质量写回节点并自适应 SF，
        # 作用于下一次 create_packet（含重传）。与 MAC 重传解耦。
        node.last_rssi = packet.rssi
        node.last_snr = packet.snr
        if config.ADR_ENABLED:
            node.sf = adapt_sf(node.sf, packet.snr)

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

        if packet.success:
            mac.handle_success()           # 成功：复位状态机
            self.received += 1
        else:
            mac.handle_failure()           # 失败：retry_count++ -> RETRY 或丢弃
            if mac.state == MacState.RETRY:
                # 可重传：进入退避并排定重发事件
                backoff = self._rng.uniform(
                    config.BACKOFF_MIN, config.BACKOFF_MAX
                )
                mac.start_backoff()        # RETRY -> WAIT_BACKOFF
                self.scheduler.add_event(
                    self.scheduler.current_time + backoff,
                    node.node_id,
                    "RETRANSMIT",
                    lambda ev, n=node: self._on_transmit(ev, n),
                )
            else:
                # 超过最大重试次数，丢弃该业务包
                self.lost += 1

    def run(self):
        """运行离散事件主循环。"""
        self.scheduler.run()

    def statistics(self):
        generated = self.generated
        received = self.received
        lost = self.lost
        retransmissions = self.retransmissions
        pdr = (received / generated * 100.0) if generated else 0.0
        throughput = (received / self.duration) if self.duration else 0.0
        return {
            "generated": generated,
            "received": received,
            "lost": lost,
            "retransmissions": retransmissions,
            "pdr": pdr,
            "throughput": throughput,
        }
