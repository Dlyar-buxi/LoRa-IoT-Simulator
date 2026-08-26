"""
Channel Model — Validation Suite (Sprint 6.3.4 · Task 2.3)

设计目标 (对应 ADR-001: "Channel Model 是物理世界抽象层, 而非传播公式集合"):

- Test 1 距离单调性:   distance↑ => RSSI↓, PDR 非增
                      防止未来模型替换 (Shadowing/Urban/ML...) 破坏基本物理规律。
- Test 2 参数敏感性:  path_loss_exponent 改变 => RSSI 改变
                      证明 config 参数真正进入模型 (而非硬编码)。
- Test 3 模型替换:    任意 ChannelModel 子类经 ChannelModelLinkAdapter 正确回填 packet
                      证明 Simulator/Adapter 只依赖 ChannelModel 抽象, 不依赖具体物理实现
                      —— 这正是 ADR-001 的核心论点。

运行:
    python -m simulator.test_channel_model_validation

注: 所有断言只使用确定性字段 (rssi / pdr); packet_received 是随机采样, 不参与断言。
"""

import random

from simulator.channel_model import (
    ChannelModel,
    ChannelModelLinkAdapter,
    ChannelResult,
    LogDistanceChannel,
    TransmissionContext,
)
from simulator.packet import Packet


class _DummyNode:
    def __init__(self, node_id="Node001"):
        self.id = node_id


class _DummyGateway:
    def __init__(self, gateway_id="GW001", x=300.0, y=0.0):
        self.id = gateway_id
        self.x = x
        self.y = y


def _make_context(
    distance: float = 500.0,
    sf: int = 7,
    tx_power: float = 14.0,
    environment: str = "suburban",
) -> TransmissionContext:
    return TransmissionContext(
        tx_node=_DummyNode(),
        rx_gateway=_DummyGateway(),
        distance=distance,
        tx_power=tx_power,
        frequency=868e6,
        spreading_factor=sf,
        bandwidth=125e3,
        environment=environment,
        timestamp=0.0,
    )


def test_distance_monotonic():
    """距离越远, RSSI 越低, PDR 非增 — 守住基本物理规律。

    对数距离模型下 RSSI 严格单调递减; PDR 在近距离饱和 (≈1.0), 故用「非增」
    断言 + 整体跨度下降, 防止稠密近距点把 PDR 误判为不下降。
    """
    random.seed(0)
    channel = LogDistanceChannel()

    distances = [10.0, 100.0, 500.0, 2000.0, 8000.0]
    results = [channel.evaluate(_make_context(distance=d)) for d in distances]

    # RSSI 严格单调递减
    for near, far in zip(results, results[1:]):
        assert near.rssi > far.rssi, (
            f"RSSI 应在距离增大时下降: {near.rssi} !> {far.rssi}"
        )
        # PDR 非增 (物理单调性; 近距饱和段允许相等)
        assert near.pdr >= far.pdr, (
            f"PDR 应在距离增大时非增: {near.pdr} < {far.pdr}"
        )

    # 整体跨度: 远距离 PDR 显著低于近距离 (证明确会下降)
    assert results[0].pdr > results[-1].pdr, (
        f"PDR 应随距离整体下降: {results[0].pdr} !> {results[-1].pdr}"
    )

    print("===== Validation Test 1: Distance Monotonicity =====")
    for d, r in zip(distances, results):
        print(f"  {d:7.1f} m  RSSI={r.rssi:7.2f} dBm  PDR={r.pdr:.4f}")
    print("  OK: distance↑ => RSSI↓, PDR↓ (物理规律守住)")


def test_parameter_sensitivity():
    """路径损耗指数 n 改变 => RSSI 改变 — 证明 config 参数真正进入模型。

    若模型把 n 硬编码 (如遗留 LoRaChannel 写死 3.0), 此测试会暴露参数无效。
    """
    random.seed(0)
    low_n = LogDistanceChannel(path_loss_exponent=2.0)
    high_n = LogDistanceChannel(path_loss_exponent=3.5)

    base = dict(distance=500.0, sf=7, tx_power=14.0, environment="suburban")
    r_low = low_n.evaluate(_make_context(**base))
    r_high = high_n.evaluate(_make_context(**base))

    # n 越大 => 路径损耗越大 => RSSI 越低; 同时 PDR 不增
    assert r_low.rssi > r_high.rssi, (
        f"n=2.0 的 RSSI 应高于 n=3.5: {r_low.rssi} !> {r_high.rssi}"
    )
    assert r_low.pdr >= r_high.pdr

    print("===== Validation Test 2: Parameter Sensitivity =====")
    print(f"  n=2.0  RSSI={r_low.rssi:.2f} dBm  PDR={r_low.pdr:.4f}")
    print(f"  n=3.5  RSSI={r_high.rssi:.2f} dBm  PDR={r_high.pdr:.4f}")
    print("  OK: path_loss_exponent 真正驱动模型输出 (config 生效)")


def test_model_substitution():
    """任意 ChannelModel 子类经 Adapter 正确回填 packet — 证明 Simulator 不依赖具体模型。

    对应 ADR-001 核心论点: 引擎/适配器只依赖 ChannelModel 抽象, 不读取任何物理实现细节。
    未来 Shadowing/Urban/ML/DigitalTwin 仅需作为 ChannelModel 子类接入, 调用点不变。
    """

    class MockChannel(ChannelModel):
        """未来模型的替身: 返回固定常量, 与任何真实物理无关。

        若适配器/调用点偷偷依赖 LogDistanceChannel 的具体字段或公式,
        这个与物理无关的 mock 就会让测试失败 —— 因此它是对 ADR-001 的逆向证明。
        """

        def evaluate(self, context: TransmissionContext) -> ChannelResult:
            return ChannelResult(
                rssi=-50.0,
                snr=10.0,
                pdr=1.0,
                packet_received=True,
                propagation_delay=0.001,
            )

    adapter = ChannelModelLinkAdapter(MockChannel())

    pkt = Packet(node_id="N1", payload={}, sf=7, tx_power=14, x=0.0, y=0.0)
    gw = _DummyGateway(x=300.0, y=0.0)
    out = adapter.calculate_link(pkt, gw)

    # 兼容旧式调用点 + 完整回填 ChannelResult 字段
    assert out is pkt
    assert out.rssi == -50.0
    assert out.snr == 10.0
    assert out.pdr == 1.0
    assert out.success is True
    assert out.packet_received is True
    assert out.propagation_delay == 0.001

    print("===== Validation Test 3: Model Substitution (Anti-Corruption) =====")
    print("  MockChannel (无物理公式) 经 ChannelModelLinkAdapter 正确回填 packet")
    print(f"  RSSI={out.rssi} SNR={out.snr} PDR={out.pdr} recv={out.packet_received}")
    print("  OK: Simulator/Adapter 不依赖具体物理模型实现 (ADR-001)")


if __name__ == "__main__":
    test_distance_monotonic()
    test_parameter_sensitivity()
    test_model_substitution()
