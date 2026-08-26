"""
ChannelResult — 统计契约验证 (Sprint 6.4 · Task 6.4.2)

单一职责: 验证 ChannelResult v1.1 (Sprint 6.4.1 经 adapter 保留的句柄)
的物理/统计契约与向后兼容面。不修改任何生产代码
(channel_model/*, adapter.py, packet.py), 仅新增本测试文件。

5 项验证:
  1. test_distance_propagates_to_result      — distance 透传到 ChannelResult
  2. test_log_distance_path_loss_monotonic   — path_loss 随距离严格递增 (确定性)
  3. test_shadowing_sigma_statistics        — 阴影经验 σ ≈ config.SHADOW_SIGMA
  4. test_rayleigh_power_statistics         — 平均线性功率增益 E[|h|^2] ≈ 1
  5. test_adapter_backward_compatibility    — packet.channel_result 与兼容面一致

防 flaky 纪律 (来自冻结):
  - Shadowing/Rayleigh 统计: 固定 seed=config.SEED, 复用**同一 channel 实例**
    重复 evaluate() N 次; 若每次重建 (同 seed) 则样本全同, 非 i.i.d.。
  - 大样本 N=2000, 宽松范围 (0.8σ~1.2σ / 均值 0.8~1.2), 杜绝精确比较。
  - 仅经公开 ChannelResult 验证统计性质, 不读任何内部变量 (_h/_rng/...)。

运行:
    python -m simulator.test_channel_result_statistics
"""

import statistics

from simulator import config
from simulator.channel_model import (
    ChannelModelLinkAdapter,
    ChannelResult,
    LogDistanceChannel,
    RayleighChannel,
    ShadowingChannel,
    TransmissionContext,
)
from simulator.packet import Packet

# 复用既有验证套件的 helper, 避免重复创建测试工具
from simulator.test_channel_model_validation import _DummyGateway, _make_context

# 统计样本数: 足够大以换取稳定的经验统计量与宽松容差兼容
N_SAMPLES = 2000


def test_distance_propagates_to_result():
    """distance 字段应原样透传到 ChannelResult (v1.1 自描述句柄)。"""
    channel = LogDistanceChannel()
    ctx = _make_context(distance=300.0, sf=7, tx_power=14.0, environment="suburban")
    result = channel.evaluate(ctx)

    assert isinstance(result, ChannelResult)
    assert result.distance == 300.0
    assert result.distance == ctx.distance
    # path_loss 同属 v1.1 新增字段, 应被填充为有限浮点
    assert isinstance(result.path_loss, float)
    assert result.path_loss > 0.0


def test_log_distance_path_loss_monotonic():
    """path_loss 应随距离严格单调递增 (确定性物理规律, 无随机)。"""
    channel = LogDistanceChannel()
    distances = [10.0, 100.0, 500.0, 2000.0, 8000.0]
    results = [channel.evaluate(_make_context(distance=d)) for d in distances]

    for near, far in zip(results, results[1:]):
        assert near.path_loss < far.path_loss, (
            f"path_loss 应随距离严格递增: {near.path_loss} !< {far.path_loss}"
        )


def test_shadowing_sigma_statistics():
    """阴影衰落经验标准差应 ≈ config.SHADOW_SIGMA (σ=4.0)。

    度量方式: shadow_i = rssi_i - base_rssi, 其中 base_rssi 由同参数
    LogDistanceChannel 提供 (无阴影基线)。固定 seed 保证可复现、非 flaky。
    """
    channel = ShadowingChannel(sigma=config.SHADOW_SIGMA, seed=config.SEED)
    baseline = LogDistanceChannel()  # 同 environment/tx_power/distance -> 同 path_loss

    shadows = []
    for _ in range(N_SAMPLES):
        ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
        r = channel.evaluate(ctx)
        base = baseline.evaluate(ctx)
        shadows.append(r.rssi - base.rssi)

    std = statistics.pstdev(shadows)
    sigma = config.SHADOW_SIGMA
    assert 0.8 * sigma < std < 1.2 * sigma, (
        f"阴影经验 σ={std:.3f} 应落在 {0.8*sigma}~{1.2*sigma} (配置 σ={sigma})"
    )


def test_rayleigh_power_statistics():
    """平均线性功率增益 E[|h|^2] 应 ≈ 1 (瑞利快衰落功率守恒)。

    由公开结果反推: rssi = base_rssi + 10·log10(|h|^2)
    => |h|^2 = 10^((rssi - base_rssi)/10)。固定 seed, 大样本均值趋于 1。
    仅经 ChannelResult 验证, 不读内部变量。
    """
    channel = RayleighChannel(seed=config.SEED)
    baseline = LogDistanceChannel()

    linear_powers = []
    for _ in range(N_SAMPLES):
        ctx = _make_context(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
        r = channel.evaluate(ctx)
        base = baseline.evaluate(ctx)
        h2 = 10.0 ** ((r.rssi - base.rssi) / 10.0)
        linear_powers.append(h2)

    mean_h2 = statistics.mean(linear_powers)
    assert 0.8 < mean_h2 < 1.2, (
        f"平均线性功率增益 E[|h|^2]={mean_h2:.3f} 应落在 0.8~1.2 (理论=1)"
    )


def test_adapter_backward_compatibility():
    """经 adapter 回填后, packet.channel_result 句柄与兼容面严格一致。

    冻结规则: success ∉ ChannelResult, 故**绝不**断言
    packet.channel_result.success; 以 packet_received == packet.success 表达等价。
    """
    channel = LogDistanceChannel()
    adapter = ChannelModelLinkAdapter(channel, environment="suburban")

    pkt = Packet(node_id="N1", payload={}, sf=7, tx_power=14, x=0.0, y=0.0)
    gw = _DummyGateway(x=300.0, y=0.0)
    out = adapter.calculate_link(pkt, gw)

    # 句柄已保留 (Sprint 6.4.1 生命周期增强)
    assert out.channel_result is not None
    # 兼容面与句柄同源, 值严格相等
    assert out.channel_result.rssi == out.rssi
    assert out.channel_result.snr == out.snr
    assert out.channel_result.packet_received == out.success
    # v1.1 自描述字段同样透传
    assert out.channel_result.distance == out.distance


if __name__ == "__main__":
    test_distance_propagates_to_result()
    test_log_distance_path_loss_monotonic()
    test_shadowing_sigma_statistics()
    test_rayleigh_power_statistics()
    test_adapter_backward_compatibility()
    print("OK: ChannelResult statistical validation passed")
