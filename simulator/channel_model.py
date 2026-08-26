"""
Channel Model — 可插拔物理世界抽象层 (Sprint 6.3.4 · Task 2.2)

接口契约冻结于:
- docs/design/channel-model-api.md
- docs/adr/ADR-001-channel-model-architecture.md

本文件提供:
- TransmissionContext  (输入契约, dataclass)
- ChannelResult        (输出契约, dataclass)
- ChannelModel(ABC)    (抽象接口 — 唯一扩展点)
- LogDistanceChannel   (v0.1 基线实现: 对数距离路径损耗)

设计约束 (来自 ADR-001 / channel-model-api.md):
- evaluate() 必须是纯函数式: 不修改 Node / Gateway / MAC, 无副作用;
  仅读取 TransmissionContext 中的字段, 不回写任何对象。
- 所有未来模型 (Shadowing / Rayleigh / Urban / ML / DigitalTwin) 均为
  ChannelModel 的子类, 调用点 (仿真引擎) 保持不变。
- 本文件为新增模块, 不修改既有 simulator/channel.py / propagation.py。

物理约定 (与 simulator/channel.py 对齐):
- SF7..SF12 接收灵敏度表
- noise_floor 默认 -120 dBm
- 参考距离 d0 = 1 m, Friis 参考损耗
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


# 物理常量
SPEED_OF_LIGHT = 3.0e8  # m/s

# LoRa 典型接收灵敏度 (dBm), SF7..SF12 — 与 simulator/channel.py 一致
SF_SENSITIVITY = {
    7: -123,
    8: -126,
    9: -129,
    10: -132,
    11: -134,
    12: -137,
}

# 环境 -> 默认路径损耗指数 (n)。
# 仅作 LogDistanceChannel 基线参考; 不改变接口契约, 可用构造参数覆盖。
ENV_PATH_LOSS_EXPONENT = {
    "urban": 3.5,
    "suburban": 3.0,
    "rural": 2.7,
    "indoor": 3.2,
}


@dataclass
class TransmissionContext:
    """单次传输的输入契约。

    由仿真引擎在 Node 发出 packet 后、Gateway 接收前构建,
    ChannelModel 绝不读取节点/网关坐标, 只消费已算好的 distance 等字段。
    """

    tx_node: "Node"            # 发送节点 (只读引用, 不修改)
    rx_gateway: "Gateway"      # 目标网关 (只读引用, 不修改)
    distance: float            # 米, 由引擎根据坐标计算
    tx_power: float            # dBm, 节点发射功率
    frequency: float           # Hz (e.g. 868e6 for EU868)
    spreading_factor: int      # SF7..SF12
    bandwidth: float           # Hz (e.g. 125e3)
    environment: str           # "urban" | "suburban" | "indoor" | "rural"
    timestamp: float           # 仿真时钟, 秒


@dataclass
class ChannelResult:
    """单次传输的输出契约。"""

    rssi: float                # dBm, 接收信号强度
    snr: float                 # dB, 信噪比
    pdr: float                 # 0..1, 包投递概率
    packet_received: bool      # 本次传输采样得到的布尔结果
    propagation_delay: float   # 秒, 单向路径时延


class ChannelModel(ABC):
    """所有信道模型的抽象基类 — 唯一的扩展点。

    新增一种传播模型 = 新增一个 ChannelModel 子类, 其余代码无需改动。
    """

    @abstractmethod
    def evaluate(self, context: TransmissionContext) -> ChannelResult:
        """计算单次传输的链路质量。

        实现必须是纯函数式: 不修改 Node / Gateway / MAC, 无副作用;
        仅返回一个 ChannelResult。
        """
        ...


class LogDistanceChannel(ChannelModel):
    """v0.1 基线实现: 对数距离路径损耗模型。

    链路: distance -> log-distance path loss -> RSSI -> SNR -> PDR
    不含阴影衰落 / 多径瑞利 / 建筑遮挡 (见 channel-model-api.md 未来实现表)。
    """

    def __init__(
        self,
        frequency: float = 868e6,
        path_loss_exponent: Optional[float] = None,
        noise_floor: float = -120.0,
        reference_distance: float = 1.0,
    ):
        """
        frequency:
            LoRa 载波频率 (Hz), EU868 默认 868e6。
        path_loss_exponent:
            路径损耗指数 n; 为 None 时按 environment 取默认 (见
            ENV_PATH_LOSS_EXPONENT), 传值则强制覆盖。
        noise_floor:
            噪声基底 (dBm), 默认 -120, 与 simulator/channel.py 一致。
        reference_distance:
            参考距离 d0 (米), 默认 1 m。
        """
        self.frequency = frequency
        self.path_loss_exponent = path_loss_exponent
        self.noise_floor = noise_floor
        self.d0 = reference_distance

    # --- 内部物理计算 (纯函数, 无副作用) ---

    def _exponent(self, environment: str) -> float:
        if self.path_loss_exponent is not None:
            return self.path_loss_exponent
        return ENV_PATH_LOSS_EXPONENT.get(environment, 3.0)

    def _reference_loss(self) -> float:
        """1 米 (d0) 参考损耗, Friis 公式。"""
        wavelength = SPEED_OF_LIGHT / self.frequency
        return 20.0 * math.log10(4.0 * math.pi * self.d0 / wavelength)

    def _path_loss(self, distance: float, environment: str) -> float:
        d = max(distance, self.d0)
        pl0 = self._reference_loss()
        n = self._exponent(environment)
        return pl0 + 10.0 * n * math.log10(d / self.d0)

    def _pdr_from_rssi(self, rssi: float, sf: int) -> float:
        """由 RSSI 与灵敏度计算平滑 PDR (0..1)。

        margin = rssi - sensitivity; sigmoid 软阈值 (软度 3 dB)。
        margin=0 时 pdr=0.5, 远大于 0 趋近 1, 远小于 0 趋近 0。
        """
        sensitivity = SF_SENSITIVITY.get(sf, -123)
        margin = rssi - sensitivity
        return 1.0 / (1.0 + math.exp(-margin / 3.0))

    # --- ChannelModel 接口实现 ---

    def evaluate(self, context: TransmissionContext) -> ChannelResult:
        # 1. 路径损耗 (对数距离)
        path_loss = self._path_loss(context.distance, context.environment)

        # 2. RSSI = 发射功率 - 路径损耗
        rssi = context.tx_power - path_loss

        # 3. SNR = RSSI - 噪声基底
        snr = rssi - self.noise_floor

        # 4. PDR (概率, 0..1)
        pdr = self._pdr_from_rssi(rssi, context.spreading_factor)

        # 5. 采样本次传输结果 (packet_received 为布尔采样)
        packet_received = random.random() < pdr

        # 6. 单向路径时延 (电磁传播时延; 若未来有 payload 可叠加 air-time)
        propagation_delay = context.distance / SPEED_OF_LIGHT

        return ChannelResult(
            rssi=round(rssi, 2),
            snr=round(snr, 2),
            pdr=round(pdr, 4),
            packet_received=packet_received,
            propagation_delay=propagation_delay,
        )


class ChannelModelLinkAdapter:
    """向后兼容桥接 (过渡层)。

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
    """

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
