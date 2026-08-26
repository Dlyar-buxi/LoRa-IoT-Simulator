"""
Channel Model — 路径损耗契约测试 (Sprint 6.3.4 · Task 5.2.1)

聚焦"路径损耗 / 大尺度传播"这一纯物理层契约, 与 test_channel_model.py
(接口契约) / test_channel_model_validation.py (端到端验证) / test_shadowing_channel.py
(阴影实现细节) 互不重复:

  1. 参考损耗一致 (d=1m): RSSI(d0) = tx_power - Friis(PL0), 与独立重算一致
  2. 距离单调 (100/500/1000m): 距离越远 RSSI 越低, PDR 不增 (确定性基线)
  3. 环境指数 (urban/suburban/rural): n 越大 → 路径损耗越大 → RSSI 越低
  4. 统计模型: Shadowing 阴影项 mean≈0 / std≈σ; Rayleigh |h|^2 ~ Exp(1) mean≈1

复用 simulator.test_channel_model._make_context, 不重复构造逻辑。

运行:
    python -m simulator.test_channel_model_path_loss
"""

import math

from simulator.channel_model import LogDistanceChannel, RayleighChannel, ShadowingChannel
from simulator.test_channel_model import _make_context


def test_reference_loss_at_d0():
    """d = d0 = 1m 时路径损耗退化为 Friis 参考损耗 PL0, RSSI = tx_power - PL0。"""
    channel = LogDistanceChannel()
    ctx = _make_context(distance=1.0, environment="suburban")

    result = channel.evaluate(ctx)

    # 独立重算 Friis 参考损耗 (与 LogDistanceChannel._reference_loss 同公式)
    wavelength = 3.0e8 / ctx.frequency
    pl0 = 20.0 * math.log10(4.0 * math.pi * 1.0 / wavelength)
    expected_rssi = round(ctx.tx_power - pl0, 2)

    assert result.rssi == expected_rssi

    print("===== Reference Loss (d=1m) Test =====")
    print(f"PL0      : {pl0:.4f} dB")
    print(f"RSSI     : {result.rssi} dBm  (expected {expected_rssi})")


def test_distance_monotonic():
    """距离越远 RSSI 越低, PDR 不增 — 对数距离模型单调性 (确定性基线)。"""
    channel = LogDistanceChannel()
    r100 = channel.evaluate(_make_context(distance=100.0))
    r500 = channel.evaluate(_make_context(distance=500.0))
    r1000 = channel.evaluate(_make_context(distance=1000.0))

    assert r100.rssi > r500.rssi > r1000.rssi
    assert r100.pdr >= r500.pdr >= r1000.pdr

    print("===== Distance Monotonic Test =====")
    print(f"100m  RSSI={r100.rssi} PDR={r100.pdr}")
    print(f"500m  RSSI={r500.rssi} PDR={r500.pdr}")
    print(f"1000m RSSI={r1000.rssi} PDR={r1000.pdr}")


def test_environment_exponent():
    """环境路径损耗指数 n: urban(3.5) > suburban(3.0) > rural(2.7);
    同距离下 n 越大 → 路径损耗越大 → RSSI 越低。"""
    channel = LogDistanceChannel()
    r_urban = channel.evaluate(_make_context(distance=500.0, environment="urban"))
    r_sub = channel.evaluate(_make_context(distance=500.0, environment="suburban"))
    r_rural = channel.evaluate(_make_context(distance=500.0, environment="rural"))

    assert r_urban.rssi < r_sub.rssi < r_rural.rssi

    print("===== Environment Exponent Test =====")
    print(f"urban    RSSI={r_urban.rssi}")
    print(f"suburban RSSI={r_sub.rssi}")
    print(f"rural    RSSI={r_rural.rssi}")


def test_statistical_models():
    """统计性质:
    - Shadowing: RSSI = 基线 + N(0, σ), 故 mean(RSSI)≈基线, std(RSSI)≈σ
    - Rayleigh : |h|^2 = 10^(fading/10) ~ Exp(1), 故 mean(|h|^2)≈1
    """
    N = 20000
    distance = 500.0
    sigma = 4.0

    # --- Shadowing ---
    shadow = ShadowingChannel(sigma=sigma, seed=12345)
    s_ctx = _make_context(distance=distance, environment="suburban")
    base_rssi = s_ctx.tx_power - shadow._path_loss(distance, "suburban")
    srssi = [shadow.evaluate(s_ctx).rssi for _ in range(N)]
    s_mean = sum(srssi) / N
    s_var = sum((x - s_mean) ** 2 for x in srssi) / N
    s_std = math.sqrt(s_var)

    assert abs(s_mean - base_rssi) < 0.2, f"Shadowing mean off: {s_mean} vs {base_rssi}"
    assert abs(s_std - sigma) < 0.2, f"Shadowing std off: {s_std} vs {sigma}"

    # --- Rayleigh ---
    rayleigh = RayleighChannel(seed=12345)
    r_ctx = _make_context(distance=distance, environment="suburban")
    r_base = r_ctx.tx_power - rayleigh._base._path_loss(distance, "suburban")
    h2_samples = []
    for _ in range(N):
        res = rayleigh.evaluate(r_ctx)
        fading_dB = res.rssi - r_base
        h2_samples.append(10.0 ** (fading_dB / 10.0))
    h2_mean = sum(h2_samples) / N

    assert abs(h2_mean - 1.0) < 0.05, f"Rayleigh E[|h|^2] off: {h2_mean}"

    print("===== Statistical Models Test =====")
    print(f"Shadowing : mean(RSSI)={s_mean:.3f} (base {base_rssi:.3f}), "
          f"std={s_std:.3f} (sigma {sigma})")
    print(f"Rayleigh  : E[|h|^2]={h2_mean:.4f} (expected 1.0)")


if __name__ == "__main__":
    test_reference_loss_at_d0()
    test_distance_monotonic()
    test_environment_exponent()
    test_statistical_models()
    print("\nAll path-loss contract tests passed.")
