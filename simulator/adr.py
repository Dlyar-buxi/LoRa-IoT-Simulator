"""
LoRa Adaptive Data Rate (ADR)

Sprint 4.2: 根据上行链路 SNR 调整节点的扩频因子（SF）。
- SNR 高（链路好）-> 降低 SF：更快、更省电
- SNR 低（链路差）-> 提高 SF：更可靠
- 双阈值 + 边界钳制，避免 SF 在临界值附近震荡，且不超过 [ADR_MIN_SF, ADR_MAX_SF]。

纯函数，便于单元测试，不依赖任何 PHY 模块。
"""

from simulator import config


def adapt_sf(current_sf, snr):
    """根据 SNR 返回调整后的 SF。

    snr > ADR_HIGH_SNR -> SF - 1（链路好，提速）
    snr < ADR_LOW_SNR  -> SF + 1（链路差，提可靠）
    否则保持不变。

    SF 钳制在 [ADR_MIN_SF, ADR_MAX_SF]。
    """
    if not config.ADR_ENABLED:
        return current_sf

    if snr > config.ADR_HIGH_SNR:
        return max(config.ADR_MIN_SF, current_sf - 1)

    if snr < config.ADR_LOW_SNR:
        return min(config.ADR_MAX_SF, current_sf + 1)

    return current_sf
