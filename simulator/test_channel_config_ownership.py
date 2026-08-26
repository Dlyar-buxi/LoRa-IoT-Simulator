"""
配置所有权冻结测试 (Sprint 6.4.4.1)

锁定边界 (docs/design/channel-config-v1.md):
- 参数优先级: 显式构造参数 (config 注入) > ENV_PATH_LOSS_EXPONENT 环境表 (fallback)
- 模型默认 fallback 保留 (ShadowingChannel sigma=7.0), 旧 API 不破坏
- 信道模型层零 config 依赖 (不 import simulator.config)
- 不改变任何计算结果, 仅验证参数解析优先级与构造兼容性

运行: python -m pytest -q simulator/test_channel_config_ownership.py
"""

import math

import pytest

from simulator import config
from simulator.channel_model import LogDistanceChannel, ShadowingChannel
from simulator.channel_model.base import ENV_PATH_LOSS_EXPONENT
from simulator.test_channel_model_validation import _make_context


def _expected_path_loss(distance: float, exponent: float) -> float:
    """复算对数距离路径损耗 (与 log_distance._path_loss 同公式), 用于断言fallback。"""
    d0 = 1.0
    wavelength = 3e8 / config.FREQUENCY
    pl0 = 20.0 * math.log10(4.0 * math.pi * d0 / wavelength)
    return pl0 + 10.0 * exponent * math.log10(distance / d0)


def test_explicit_exponent_overrides_environment():
    """显式 path_loss_exponent 优先级高于 environment fallback。

    即使用 environment='urban' (其表值 3.5), 显式 2.0 也必须胜出。
    """
    ctx = _make_context(distance=1000.0, sf=7, tx_power=14.0, environment="urban")
    channel = LogDistanceChannel(path_loss_exponent=2.0)
    result = channel.evaluate(ctx)
    assert result.path_loss == pytest.approx(_expected_path_loss(1000.0, 2.0))
    # 关键: 不受 environment='urban' 表值 3.5 影响
    assert result.path_loss != pytest.approx(
        _expected_path_loss(1000.0, ENV_PATH_LOSS_EXPONENT["urban"])
    )


def test_environment_fallback_selects_exponent():
    """无显式 exponent 时, 按 ENV_PATH_LOSS_EXPONENT[environment] 选指数。"""
    for env, n_expected in ENV_PATH_LOSS_EXPONENT.items():
        ctx = _make_context(distance=1000.0, sf=7, tx_power=14.0, environment=env)
        channel = LogDistanceChannel()  # 无显式 exponent -> fallback
        result = channel.evaluate(ctx)
        assert result.path_loss == pytest.approx(
            _expected_path_loss(1000.0, n_expected)
        ), f"env={env}"


def test_shadowing_default_sigma_is_fallback():
    """ShadowingChannel() 仍使用默认 sigma=7.0 (fallback), 旧 API 不破坏。"""
    legacy = ShadowingChannel()
    assert legacy.sigma == 7.0
    # 官方路径: 显式注入 config.SHADOW_SIGMA (4.0)
    official = ShadowingChannel(sigma=config.SHADOW_SIGMA)
    assert official.sigma == config.SHADOW_SIGMA
    # 两者都可正常 evaluate (向后兼容)
    ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    assert legacy.evaluate(ctx) is not None
    assert official.evaluate(ctx) is not None


def test_shadowing_explicit_sigma_overrides_fallback():
    """显式 sigma 确实生效 (config 注入路径有效), 与默认 fallback 区分。"""
    ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    low = ShadowingChannel(sigma=2.0, seed=1)
    high = ShadowingChannel(sigma=12.0, seed=1)  # 同 seed, 不同 sigma
    rssi_low = low.evaluate(ctx).rssi
    rssi_high = high.evaluate(ctx).rssi
    assert rssi_low != rssi_high  # sigma 参数被尊重 (config 注入路径有效)


def test_channel_model_layer_has_no_config_dependency():
    """信道模型层不得 import simulator.config (保持 6.4.4.0 解耦边界)。"""
    import simulator.channel_model as pkg
    import simulator.channel_model.adapter as adapter
    import simulator.channel_model.base as base
    import simulator.channel_model.log_distance as log_distance
    import simulator.channel_model.rayleigh as rayleigh
    import simulator.channel_model.shadowing as shadowing

    for mod in (pkg, base, log_distance, shadowing, rayleigh, adapter):
        assert "config" not in getattr(mod, "__dict__", {}), (
            f"{mod.__name__} 不应 import simulator.config"
        )
