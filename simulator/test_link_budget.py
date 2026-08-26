"""
LinkBudget 分解层验证 (Sprint 6.4 · Task 6.4.3.1)

单一职责: 验证 LinkBudgetResult 正确解释三模型的公开输出,
守住 docs/design/link-budget-v1.md 冻结的不变量与填充规则。

纪律:
- 仅消费公开 ChannelResult / context; 不访问模型内部随机变量。
- 复用 simulator.test_channel_model_validation 的 _make_context (不重复造工具)。
- Shadowing / Rayleigh 用同一实例 + 固定 config.SEED 重复 evaluate -> 非 flaky。
- 模型 rssi 四舍五入到 2 位小数, 故涉及 rssi 的等式用 pytest.approx(abs=0.01/0.02)。
"""

import statistics

import pytest

from simulator import config
from simulator.channel_model.link_budget import (
    LinkBudgetResult,
    db_to_linear,
    decompose,
    linear_to_db,
)
from simulator.channel_model.log_distance import LogDistanceChannel
from simulator.channel_model.rayleigh import RayleighChannel
from simulator.channel_model.shadowing import ShadowingChannel
from simulator.test_channel_model_validation import _make_context


def test_log_distance_budget_decomposition():
    """LogDistance: 无阴影 / 无快衰落。

    shadowing_loss == 0
    fading_gain == 0
    received_power == tx_power - path_loss
    """
    ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    channel = LogDistanceChannel()
    lb = decompose(channel, ctx)

    assert lb.shadowing_loss == 0.0
    assert lb.fading_gain == 0.0
    # received_power == tx_power - path_loss (rssi 四舍五入到 2 位, 容差 0.01)
    assert lb.received_power == pytest.approx(ctx.tx_power - lb.path_loss, abs=0.01)


def test_shadowing_budget_decomposition():
    """Shadowing: shadowing_loss == 相对 baseline LogDistance 的偏移。

    使用 ShadowingChannel(sigma=config.SHADOW_SIGMA, seed=config.SEED),
    不重新定义任何参数。
    """
    ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    channel = ShadowingChannel(sigma=config.SHADOW_SIGMA, seed=config.SEED)
    lb = decompose(channel, ctx)

    # 相对同参数 baseline LogDistance 的偏移
    baseline = LogDistanceChannel().evaluate(ctx)
    expected = lb.received_power - baseline.rssi
    assert lb.shadowing_loss == pytest.approx(expected, abs=0.02)
    assert lb.fading_gain == 0.0
    # baseline 自身满足 received_power == tx_power - path_loss
    assert baseline.rssi == pytest.approx(
        ctx.tx_power - baseline.path_loss, abs=0.01
    )


def test_rayleigh_budget_fading_statistics():
    """Rayleigh: 平均线性 fading_gain E[|h|^2] ≈ 1 (仅经公开 ChannelResult)。

    不访问内部随机变量; 同一实例 + 固定 config.SEED 重复 evaluate 得 i.i.d. 样本。
    """
    ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    channel = RayleighChannel(seed=config.SEED)

    N = 2000
    linear_gains = []
    for _ in range(N):
        lb = decompose(channel, ctx)
        linear_gains.append(db_to_linear(lb.fading_gain))

    mean_gain = statistics.mean(linear_gains)
    # E[|h|^2] = 1, 宽松统计范围避免 flaky
    assert 0.8 < mean_gain < 1.2
    # 每个样本的 fading_gain 必须非零 (快衰落确实存在)
    assert all(g != 0.0 for g in linear_gains)


def test_core_invariant_holds_for_all_models():
    """核心不变量: received_power == tx_power - path_loss + shadowing + fading。

    对三模型逐一成立; 并附带校验 dB/linear 辅助互逆。
    """
    ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    models = [
        LogDistanceChannel(),
        ShadowingChannel(sigma=config.SHADOW_SIGMA, seed=config.SEED),
        RayleighChannel(seed=config.SEED),
    ]
    for channel in models:
        lb = decompose(channel, ctx)
        expected = (
            ctx.tx_power - lb.path_loss + lb.shadowing_loss + lb.fading_gain
        )
        assert lb.received_power == pytest.approx(expected, abs=0.01)

    # dB / linear 辅助互逆 (分解层公共工具契约)
    assert db_to_linear(linear_to_db(2.0)) == pytest.approx(2.0)
    assert linear_to_db(db_to_linear(-3.0)) == pytest.approx(-3.0)
