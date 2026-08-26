"""
ChannelModelLinkAdapter — 向后兼容桥接 (过渡层)

把新的 ChannelModel.evaluate(context) 包装成旧式
calculate_link(packet, gateway) 调用点, 使现有仿真编排
(simulator/simulation.py, simulator/gateway_selector.py) 无需改动即可
接入 Channel Model v0.1。

职责 (对应 ADR-001 "引擎构建 TransmissionContext"):
- 计算 distance (引擎职责)
- 由 packet / gateway 字段构建 TransmissionContext
- 调用 ChannelModel.evaluate()
- 把 ChannelResult 回填到 packet (兼容既有 rssi/snr/success 语义)

注意: 这是过渡适配器; 未来调用点直接构建 TransmissionContext 后可移除。
ChannelModel 自身保持纯净 (仅 evaluate), 本适配器不污染其接口。

包结构重构 (Task 2.4) 后从 simulator/channel_model.py 迁入本文件, 逻辑不变。
"""

from __future__ import annotations

import math

from simulator.channel_model.base import (
    ChannelModel,
    ChannelResult,
    TransmissionContext,
)


class ChannelModelLinkAdapter:
    """向后兼容桥接 (过渡层)。"""

    def __init__(self, model: ChannelModel, environment: str = "suburban"):
        self.model = model
        self.environment = environment

    def calculate_link(self, packet, gateway) -> object:
        """兼容旧式调用点: 计算单次上行链路并回填 packet。"""
        # 1. 引擎职责: 由坐标计算距离
        distance = math.hypot(
            packet.x - gateway.x,
            packet.y - gateway.y,
        )

        # 2. 构建 TransmissionContext (只读 packet / gateway 字段)
        #    tx_node 以 packet 作为发送方引用传入 (模型只消费 tx_power 等
        #    上下文字段, 绝不修改该引用)。
        context = TransmissionContext(
            tx_node=packet,
            rx_gateway=gateway,
            distance=distance,
            tx_power=packet.tx_power,
            frequency=packet.frequency,
            spreading_factor=packet.sf,
            bandwidth=packet.bandwidth,
            environment=self.environment,
            timestamp=packet.timestamp,
        )

        # 3. 评估
        result = self.model.evaluate(context)

        # 3.1 保存完整 ChannelResult 句柄 (Sprint 6.4 生命周期增强)
        #     下游既可继续读 packet.rssi / snr / success 兼容面, 也可经
        #     packet.channel_result 访问自描述完整结果 (distance / path_loss 等),
        #     无需回查 TransmissionContext。旧消费者零改动。
        packet.channel_result = result

        # 4. 回填 packet (兼容既有字段语义 + 新增 ChannelResult 字段)
        packet.distance = round(distance, 2)
        packet.gateway_id = gateway.id
        packet.rssi = result.rssi
        packet.snr = result.snr
        packet.success = result.packet_received
        packet.pdr = result.pdr
        packet.packet_received = result.packet_received
        packet.propagation_delay = result.propagation_delay
        return packet
