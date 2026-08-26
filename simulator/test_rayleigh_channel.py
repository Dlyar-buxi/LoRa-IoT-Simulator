"""
RayleighChannel — 验证套件 (Sprint 6.3.4 · Task 4.4)

运行:
    python -m simulator.test_rayleigh_channel
"""

import math

from simulator.channel_model import (
    ChannelModel,
    ChannelModelLinkAdapter,
    ChannelResult,
    LogDistanceChannel,
    RayleighChannel,
    SF_SENSITIVITY,
    ShadowingChannel,
)
from simulator.packet import Packet
from simulator.test_channel_model import _make_context


def test_contract():
    """RayleighChannel 满足 ChannelModel 契约, 且与 LogDistanceChannel 类型平行。"""
    ch = RayleighChannel(seed=1)
    ctx = _make_context(distance=400.0)
    r = ch.evaluate(ctx)

    assert isinstance(r, ChannelResult)
    assert set(vars(r).keys()) == {
        "rssi",
        "snr",
        "pdr",
        "packet_received",
        "propagation_delay",
        "distance",
        "path_loss",
    }
    # 扩展点正确, 且为 ChannelModel 子类
    assert isinstance(ch, ChannelModel)
    # 类型平行 (HAS-A 组合而非 IS-A 继承), 不继承 LogDistance 随机项
    assert not isinstance(ch, LogDistanceChannel)
    # 物理基本性质
    assert r.rssi < ctx.tx_power
    assert 0.0 <= r.pdr <= 1.0
    assert r.propagation_delay > 0.0

    print("===== Rayleigh Contract Test =====")
    print(f"RSSI={r.rssi} SNR={r.snr} PDR={r.pdr} recv={r.packet_received}")


def test_seed_reproducibility():
    """相同 seed -> 相同调用序列产生相同 RSSI/SNR/PDR/received; 不同 seed 不一致。"""
    a = RayleighChannel(seed=42)
    b = RayleighChannel(seed=42)
    c = RayleighChannel(seed=43)
    ctx = _make_context(distance=300.0)

    seq_a, seq_b, seq_c = [], [], []
    for _ in range(50):
        ra, rb, rc = a.evaluate(ctx), b.evaluate(ctx), c.evaluate(ctx)
        seq_a.append((ra.rssi, ra.snr, ra.pdr, ra.packet_received))
        seq_b.append((rb.rssi, rb.snr, rb.pdr, rb.packet_received))
        seq_c.append((rc.rssi, rc.snr, rc.pdr, rc.packet_received))

    assert seq_a == seq_b, "same seed must reproduce identical sequence"
    assert seq_a != seq_c, "different seed must produce different sequence"
    print("===== Seed Reproducibility Test =====")
    print("same seed -> identical over 50 evals; different seed -> differs: OK")


def test_fading_distribution():
    """5000 样本: |h|^2 = -ln(U) 服从 Exp(1) (均值≈1), 包络 |h| 服从 Rayleigh。"""
    base = LogDistanceChannel(frequency=868e6, path_loss_exponent=2.8, noise_floor=-120.0)
    rayleigh = RayleighChannel(
        frequency=868e6, path_loss_exponent=2.8, noise_floor=-120.0, seed=2024
    )
    ctx = _make_context(distance=400.0)
    base_rssi = base.evaluate(ctx).rssi  # 确定性基线

    h2 = []  # 恢复的 |h|^2 = 10^((rssi - base_rssi)/10)
    N = 5000
    for _ in range(N):
        rssi = rayleigh.evaluate(ctx).rssi
        fading_dB = rssi - base_rssi
        h2.append(10.0 ** (fading_dB / 10.0))

    mean_h2 = sum(h2) / N
    assert abs(mean_h2 - 1.0) < 0.05, f"mean |h|^2 = {mean_h2} not ~1.0"

    # 经验 CDF 分位数 vs 理论 Exp(1): q(p) = -ln(1-p)
    h2_sorted = sorted(h2)
    for p in (0.25, 0.5, 0.75, 0.9):
        emp = h2_sorted[int(p * (N - 1))]
        theo = -math.log(1.0 - p)
        assert abs(emp - theo) / theo < 0.08, (
            f"p={p}: empirical {emp:.3f} vs theoretical {theo:.3f}"
        )

    print("===== Fading Distribution Test (5000 samples) =====")
    print(f"mean |h|^2 = {mean_h2:.4f} (expect ~1.0, Exp(1))")
    print("empirical CDF quantiles match Rayleigh/Exp(1) within 8%: OK")


def test_mean_power_recovery():
    """Rayleigh 零均值归一化: 平均 *线性* 接收功率 = 无衰落基线 (dB 均值下偏属正常)。"""
    base = LogDistanceChannel(frequency=868e6, path_loss_exponent=2.8, noise_floor=-120.0)
    rayleigh = RayleighChannel(
        frequency=868e6, path_loss_exponent=2.8, noise_floor=-120.0, seed=777
    )
    ctx = _make_context(distance=400.0)
    base_rssi = base.evaluate(ctx).rssi
    base_linear = 10.0 ** (base_rssi / 10.0)

    samples = []
    for _ in range(20000):
        r = rayleigh.evaluate(ctx)
        samples.append(10.0 ** (r.rssi / 10.0))
    mean_linear = sum(samples) / len(samples)

    assert abs(mean_linear - base_linear) / base_linear < 0.05, (
        f"mean linear power {mean_linear:.2f} deviates >5% from baseline {base_linear:.2f}"
    )
    print("===== Mean Power Recovery Test (Rayleigh 'degenerate') =====")
    print(f"mean(10^(RSSI/10)) = {mean_linear:.3e} vs baseline {base_linear:.3e} "
          "(<5% dev): OK")


def test_monte_carlo_benchmark():
    """Monte Carlo 对照: LogDistance / Shadowing / Rayleigh 覆盖概率 & 平均 PDR。"""
    freq, ple, nf = 868e6, 2.8, -120.0
    base = LogDistanceChannel(frequency=freq, path_loss_exponent=ple, noise_floor=nf)
    shadow = ShadowingChannel(
        frequency=freq, path_loss_exponent=ple, noise_floor=nf, sigma=7.0, seed=99
    )
    rayleigh = RayleighChannel(
        frequency=freq, path_loss_exponent=ple, noise_floor=nf, seed=99
    )
    N = 5000
    cases = [(100.0, 7), (300.0, 7), (1000.0, 7), (3000.0, 7)]

    print(f"===== Monte Carlo Benchmark (N={N}, seed=99) =====")
    print(f"{'dist(m)':>8} | {'model':<16} | {'cov%':>6} | {'meanPDR':>7}")
    rows = []
    for dist, sf in cases:
        ctx = _make_context(distance=dist, sf=sf)
        sens = SF_SENSITIVITY[sf]
        for name, ch in (("LogDistance", base), ("Shadowing(s=7)", shadow), ("Rayleigh", rayleigh)):
            cov = sum(1 for _ in range(N) if ch.evaluate(ctx).rssi > sens)
            cov_pct = 100.0 * cov / N
            pdr_sum = sum(ch.evaluate(ctx).pdr for _ in range(N))
            mean_pdr = pdr_sum / N
            print(f"{dist:>8} | {name:<16} | {cov_pct:>6.1f} | {mean_pdr:>7.3f}")
            rows.append((dist, name, cov_pct, mean_pdr))

    # 物理合理性断言
    near_ctx = _make_context(distance=100.0, sf=7)
    for ch in (base, shadow, rayleigh):
        cov = sum(1 for _ in range(2000) if ch.evaluate(near_ctx).rssi > SF_SENSITIVITY[7]) / 2000.0
        assert cov > 0.99, f"near-field coverage {cov} should be ~100%"
    # Rayleigh 确实在施加快衰落: 500 样本 RSSI 起伏 > 5 dB
    rssis = [rayleigh.evaluate(near_ctx).rssi for _ in range(500)]
    assert max(rssis) - min(rssis) > 5.0, "Rayleigh must produce fast-fading spread"
    print("near-field coverage ~100% for all models; Rayleigh spread >5 dB: OK")


def test_adapter_integration():
    """RayleighChannel 经 ChannelModelLinkAdapter 接入, 仿真调用点零改动。"""
    channel = ChannelModelLinkAdapter(RayleighChannel(seed=2026))

    class _GW:
        def __init__(self):
            self.id = "GW1"
            self.x = 300.0
            self.y = 0.0

    pkt = Packet(node_id="N1", payload={}, sf=7, tx_power=14, x=0.0, y=0.0)
    out = channel.calculate_link(pkt, _GW())

    assert out is pkt
    assert out.rssi is not None
    assert out.snr is not None
    assert out.gateway_id == "GW1"
    assert out.pdr is not None
    assert out.packet_received is not None
    assert out.propagation_delay > 0.0
    print("===== Rayleigh via Adapter Test (ADR-001 实证) =====")
    print(f"RSSI={out.rssi} SNR={out.snr} PDR={out.pdr} recv={out.packet_received}")


if __name__ == "__main__":
    test_contract()
    test_seed_reproducibility()
    test_fading_distribution()
    test_mean_power_recovery()
    test_monte_carlo_benchmark()
    test_adapter_integration()
