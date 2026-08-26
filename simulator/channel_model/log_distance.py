"""
LogDistanceChannel — 对数距离路径损耗基线 (Sprint 6.3.4 · Task 2.2)

真实实现对 TransmissionContext/ChannelResult 契约的 v0.1 实现。
包结构重构 (Task 2.4) 后从 simulator/channel_model.py 迁入本文件, 逻辑不变。
"""

from __future__ import annotations

import math
import random

from simulator.channel_model.base import (
    ENV_PATH_LOSS_EXPONENT,
    SF_SENSITIVITY,
    SPEED_OF_LIGHT,
    ChannelModel,
    ChannelResult,
    TransmissionContext,
)


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
