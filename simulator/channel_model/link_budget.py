"""
LinkBudget — 链路预算分解 / 解释层 (Sprint 6.4 · Task 6.4.3.1)

职责 (设计冻结 docs/design/link-budget-v1.md):
- 把 ChannelModel.evaluate() 的公开 ChannelResult 输出, 分解为一份
  可解释的链路预算状态 (LinkBudgetResult), 不改变任何物理输出。
- 仅解释 / 分解 / 记录 / 验证: 不修改 RSSI/SNR/PDR, 不访问随机内部量,
  不改动三模型 / adapter / simulation。

分解原理 (全部基于公开输出, 无任何模型内部依赖):
- 每个模型的 ChannelResult 已携带 path_loss 与 rssi;
- 纯对数距离基线分量 base_rssi = tx_power - path_loss;
- delta = rssi - base_rssi 即「超出纯对数距离的额外增益 / 损耗」:
    * LogDistance:  delta == 0          -> shadowing_loss = 0, fading_gain = 0
    * Shadowing:    delta == shadow     -> shadowing_loss = delta, fading_gain = 0
    * Rayleigh:     delta == fading_dB  -> shadowing_loss = 0,   fading_gain = delta
- dB 域不变量: received_power = tx_power - path_loss + shadowing_loss + fading_gain
  由于 delta 由 rssi 定义, 该式恒等成立 -> 仅证明分解自洽, 不改物理输出。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from simulator.channel_model.base import (
    ChannelModel,
    ChannelResult,
    TransmissionContext,
)
from simulator.channel_model.log_distance import LogDistanceChannel
from simulator.channel_model.rayleigh import RayleighChannel
from simulator.channel_model.shadowing import ShadowingChannel


@dataclass
class LinkBudgetResult:
    """单次传输的链路预算解释。

    字段是「链路预算过程的可解释状态」, 不是新的 packet API
    (见 docs/design/link-budget-v1.md §5)。所有功率量均为 dBm/dB,
    唯 fading_gain 为 dB 域瑞利快衰落贡献 (10·log10(|h|^2)); 其线性化
    db_to_linear(fading_gain) = |h|^2 ~ Exp(1), 均值 1。
    """

    tx_power: float          # dBm, 发射功率 (来自 context.tx_power)
    frequency: float         # Hz, 载波频率 (来自 context.frequency)
    bandwidth: float         # Hz, 带宽 (来自 context.bandwidth)
    distance: float          # m, 传播距离 (来自 context.distance)

    path_loss: float         # dB, 大尺度对数距离路径损耗 PL(d) (来自 result.path_loss)
    shadowing_loss: float = 0.0   # dB, 高斯阴影偏移 (仅 ShadowingChannel 非零)
    fading_gain: float = 0.0      # dB, 瑞利快衰落贡献 (仅 RayleighChannel 非零)

    received_power: float = 0.0   # dBm, 接收信号强度 (== result.rssi)
    noise_power: float = 0.0      # dBm, 噪声基底 (== rssi - snr, 即 noise_floor)
    snr: float = 0.0              # dB, 信噪比 (== result.snr)


def db_to_linear(db: float) -> float:
    """dB -> 线性功率比。用于 Rayleigh fading_gain 的线性化统计检验。"""
    return 10.0 ** (db / 10.0)


def linear_to_db(lin: float) -> float:
    """线性功率比 -> dB。"""
    return 10.0 * math.log10(lin)


def decompose(model: ChannelModel, context: TransmissionContext) -> LinkBudgetResult:
    """把任一 ChannelModel 的公开输出分解为 LinkBudgetResult。

    仅消费 model.evaluate() 的公开 ChannelResult 与 context 字段,
    不访问模型内部随机量, 不改变任何物理输出。

    Args:
        model: 任意 ChannelModel 子类实例 (LogDistance / Shadowing / Rayleigh)。
        context: 与 model.evaluate() 兼容的 TransmissionContext。

    Returns:
        LinkBudgetResult, 自洽于 model 的物理输出。
    """
    result: ChannelResult = model.evaluate(context)

    # 纯对数距离基线分量 (无阴影 / 无快衰落)
    base_rssi = context.tx_power - result.path_loss
    # 「额外增益 / 损耗」= rssi 中超出纯对数距离的部分
    delta = result.rssi - base_rssi

    shadowing_loss = 0.0
    fading_gain = 0.0
    if isinstance(model, ShadowingChannel):
        shadowing_loss = delta
    elif isinstance(model, RayleighChannel):
        fading_gain = delta
    # 普通 LogDistanceChannel (非 Shadowing): delta 因 rssi 四舍五入为微小残差,
    # 但 shadowing_loss / fading_gain 显式置 0, 不携带该残差。

    return LinkBudgetResult(
        tx_power=context.tx_power,
        frequency=context.frequency,
        bandwidth=context.bandwidth,
        distance=context.distance,
        path_loss=result.path_loss,
        shadowing_loss=shadowing_loss,
        fading_gain=fading_gain,
        received_power=result.rssi,
        noise_power=result.rssi - result.snr,
        snr=result.snr,
    )
