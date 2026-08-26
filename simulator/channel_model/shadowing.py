"""
ShadowingChannel — 对数距离 + 高斯阴影衰落 (Sprint 6.3.4 · Task 3.2)

包结构重构 (Task 2.4) 后从 simulator/shadowing_channel.py 迁入本文件, 逻辑不变。

物理:
    PL(d) = PL(d0) + 10·n·log10(d/d0) + X_σ,  X_σ ~ N(0, σ)
复用 LogDistanceChannel 的 _path_loss / _pdr_from_rssi, 仅对 RSSI 叠加
高斯阴影后重算 SNR/PDR。TransmissionContext / ChannelResult 契约不变。

纪律:
- sigma=0 时与 LogDistanceChannel 的 rssi/snr/pdr 逐字节等价 (向后兼容)。
- evaluate() 纯函数式, 不修改 context / Node / Gateway。
"""

from __future__ import annotations

import random
from typing import Optional

from simulator.channel_model.base import (
    ChannelResult,
    SPEED_OF_LIGHT,
    TransmissionContext,
)
from simulator.channel_model.log_distance import LogDistanceChannel


class ShadowingChannel(LogDistanceChannel):
    """第二个物理模型: 对数距离路径损耗 + 高斯阴影衰落。

    在 LogDistanceChannel 基线之上叠加对数正态阴影 X_σ ~ N(0, σ)。
    sigma=0 时该模型逐字节退化为 LogDistanceChannel (rssi/snr/pdr 完全一致)。
    """

    def __init__(
        self,
        frequency: float = 868e6,
        path_loss_exponent: Optional[float] = None,
        noise_floor: float = -120.0,
        reference_distance: float = 1.0,
        sigma: float = 7.0,
        seed=None,
    ):
        """
        sigma:
            阴影标准差 σ (dB); 典型 4~8 dB。σ=0 退化为 LogDistanceChannel。
        seed:
            int 时确定性复现; None 走系统熵 (非确定)。
        """
        super().__init__(frequency, path_loss_exponent, noise_floor, reference_distance)
        self.sigma = float(sigma)
        self.seed = seed
        # 私有 RNG: 同时驱动阴影采样与 packet_received 采样, 保证完全复现,
        # 且不污染全局 random 流 (与 LogDistanceChannel 解耦)。
        self._rng = random.Random(seed)

    # --- ChannelModel 接口实现 (覆盖 evaluate, 复用父类物理计算) ---

    def evaluate(self, context: TransmissionContext) -> ChannelResult:
        # 1. 复用 LogDistanceChannel 的对数距离路径损耗
        path_loss = self._path_loss(context.distance, context.environment)

        # 2. 基线 RSSI (未含阴影)
        base_rssi = context.tx_power - path_loss

        # 3. 高斯阴影衰落 (X_σ ~ N(0, σ)); sigma=0 时恒为 0.0
        shadow = self._rng.gauss(0.0, self.sigma)
        rssi = base_rssi + shadow

        # 4. SNR / PDR (与 LogDistanceChannel 同公式, 基于阴影后 RSSI)
        snr = rssi - self.noise_floor
        pdr = self._pdr_from_rssi(rssi, context.spreading_factor)

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
            distance=context.distance,
            path_loss=path_loss,
        )
