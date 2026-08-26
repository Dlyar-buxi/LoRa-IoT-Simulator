"""
RayleighChannel — 对数距离路径损耗 + 小尺度瑞利快衰落 (Sprint 6.3.4 · Task 4)

物理:
    PL(d) = PL(d0) + 10·n·log10(d/d0)        (大尺度路径损耗, 复用 LogDistanceChannel)
    h ~ CN(0, 1)  ⇒  |h|^2 ~ Exp(1)  ⇒  fading_dB = 10·log10(|h|^2)
    rssi  = tx_power - PL(d) + fading_dB
    snr   = rssi - noise_floor
    pdr   = sigmoid((rssi - sensitivity) / 3)   (复用 LogDistanceChannel._pdr_from_rssi)

与 ShadowingChannel 的区别: Shadowing 是大尺度慢衰落 (IS-A LogDistanceChannel),
Rayleigh 是小尺度快衰落, 物理意义不同, 故本模型**不继承 LogDistance 的随机项**,
而是作为独立的 ChannelModel 子类, 仅通过组合复用其确定性路径损耗数学
(组合优于继承)。

纪律:
- evaluate() 纯函数式, 不修改 context / Node / Gateway。
- 随机性完全自有: self._rng 同时驱动快衰落抽样与 packet_received 采样,
  不污染全局 random (与 LogDistanceChannel / ShadowingChannel 解耦)。
- sigma=0 退化不适用 (Rayleigh 为零均值归一化); 其"退化"等价于对快衰落取统计平均,
  平均线性接收功率 = 无衰落基线 (见 docs/design/rayleigh-channel.md §4)。
"""

from __future__ import annotations

import math
import random
from typing import Optional

from simulator.channel_model.base import (
    ChannelModel,
    ChannelResult,
    SPEED_OF_LIGHT,
    TransmissionContext,
)
from simulator.channel_model.log_distance import LogDistanceChannel


class RayleighChannel(ChannelModel):
    """第三个物理模型: 对数距离路径损耗 + 小尺度瑞利多径快衰落。

    大尺度路径损耗委托给内部 LogDistanceChannel (确定性数学复用), 小尺度
    瑞利快衰落由本类私有 RNG 独立驱动。平均功率增益 E[|h|^2]=1, 故平均线性
    接收功率守恒; RSSI 在 dB 域围绕基线快速波动。
    """

    def __init__(
        self,
        frequency: float = 868e6,
        path_loss_exponent: Optional[float] = None,
        noise_floor: float = -120.0,
        reference_distance: float = 1.0,
        seed=None,
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
        seed:
            int 时确定性复现; None 走系统熵 (非确定)。
        """
        # 仅复用 LogDistanceChannel 的 *确定性* 路径损耗数学 (DRY, 不继承其随机项)
        self._base = LogDistanceChannel(
            frequency, path_loss_exponent, noise_floor, reference_distance
        )
        self.frequency = frequency
        self.noise_floor = noise_floor
        self.seed = seed
        # 私有 RNG: 独占驱动快衰落抽样与 packet_received 采样, 不污染全局 random
        self._rng = random.Random(seed)

    # --- ChannelModel 接口实现 (覆盖 evaluate, 组合复用父类物理计算) ---

    def evaluate(self, context: TransmissionContext) -> ChannelResult:
        # 1. 复用 LogDistanceChannel 的确定性对数距离路径损耗
        path_loss = self._base._path_loss(context.distance, context.environment)

        # 2. 基线 RSSI (未含快衰落)
        base_rssi = context.tx_power - path_loss

        # 3. 小尺度瑞利快衰落: |h|^2 = -ln(U), U ~ Uniform(0, 1)  ⇒  Exp(1) (均值 1)
        #    等价于从 h ~ CN(0,1) 取 |h|^2, 平均功率增益 = 1 (0 dB 均值, dB 域因
        #    Jensen 不等式下偏约 -2.5 dB, 属正常, 见设计文档 §4)。
        h2 = -math.log(self._rng.random())
        fading_dB = 10.0 * math.log10(h2)
        rssi = base_rssi + fading_dB

        # 4. SNR / PDR (与 LogDistanceChannel 同公式, 基于快衰落后 RSSI)
        snr = rssi - self.noise_floor
        pdr = self._base._pdr_from_rssi(rssi, context.spreading_factor)

        # 5. 本次传输结果采样 (由私有 RNG 驱动, 可复现)
        packet_received = self._rng.random() < pdr

        # 6. 单向传播时延 (与 LogDistanceChannel 一致)
        propagation_delay = context.distance / SPEED_OF_LIGHT

        return ChannelResult(
            rssi=round(rssi, 2),
            snr=round(snr, 2),
            pdr=round(pdr, 4),
            packet_received=packet_received,
            propagation_delay=propagation_delay,
        )
