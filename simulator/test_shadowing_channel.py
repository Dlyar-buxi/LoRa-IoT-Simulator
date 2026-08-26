"""
ShadowingChannel — 验证套件 (Sprint 6.3.4 · Task 3.3)

运行:
    python -m simulator.test_shadowing_channel
"""

import math

from simulator.channel_model import ChannelResult, LogDistanceChannel
from simulator.channel_model import ShadowingChannel
from simulator.test_channel_model import _make_context


def test_seed_reproducibility():
    """相同 seed -> 相同调用序列产生相同 RSSI/SNR/PDR/received。"""
    ch_a = ShadowingChannel(sigma=7.0, seed=42)
    ch_b = ShadowingChannel(sigma=7.0, seed=42)
    ctx = _make_context(distance=300.0)
    for _ in range(50):
        ra = ch_a.evaluate(ctx)
        rb = ch_b.evaluate(ctx)
        assert ra.rssi == rb.rssi
        assert ra.snr == rb.snr
        assert ra.pdr == rb.pdr
        assert ra.packet_received == rb.packet_received
    print("===== Seed Reproducibility Test =====")
    print("same seed -> identical RSSI/SNR/PDR/received over 50 evals: OK")


def test_shadow_distribution():
    """1000 样本: 阴影均值≈0, 标准差≈σ。"""
    base = LogDistanceChannel(frequency=868e6, path_loss_exponent=2.8, noise_floor=-120.0)
    shadow = ShadowingChannel(
        frequency=868e6, path_loss_exponent=2.8,
        noise_floor=-120.0, sigma=7.0, seed=2024,
    )
    ctx = _make_context(distance=400.0)
    shadows = []
    for _ in range(1000):
        base_rssi = base.evaluate(ctx).rssi
        sh_rssi = shadow.evaluate(ctx).rssi
        shadows.append(sh_rssi - base_rssi)
    n = len(shadows)
    mean = sum(shadows) / n
    var = sum((s - mean) ** 2 for s in shadows) / (n - 1)
    std = math.sqrt(var)
    assert abs(mean) < 0.3, f"shadow mean={mean} not ~0"
    assert abs(std - 7.0) < 0.4, f"shadow std={std} not ~7.0"
    print("===== Shadow Distribution Test (1000 samples) =====")
    print(f"mean={mean:.3f} dB (expect ~0), std={std:.3f} dB (expect ~7.0)")


def test_backward_compat_sigma0():
    """sigma=0 时 ShadowingChannel 与 LogDistanceChannel 的 rssi/snr/pdr 逐字节等价。"""
    shadow = ShadowingChannel(sigma=0.0, seed=1)
    base = LogDistanceChannel()
    ctx = _make_context(distance=300.0)
    rs = shadow.evaluate(ctx)
    rb = base.evaluate(ctx)
    assert isinstance(rs, ChannelResult)
    assert rs.rssi == rb.rssi
    assert rs.snr == rb.snr
    assert rs.pdr == rb.pdr
    print("===== Backward Compat Test (sigma=0 == LogDistanceChannel) =====")
    print(f"shadow rssi={rs.rssi} snr={rs.snr} pdr={rs.pdr}")
    print(f"base   rssi={rb.rssi} snr={rb.snr} pdr={rb.pdr}")
    print("rssi/snr/pdr identical (sigma=0 degenerates to LogDistance): OK")


if __name__ == "__main__":
    test_seed_reproducibility()
    test_shadow_distribution()
    test_backward_compat_sigma0()
