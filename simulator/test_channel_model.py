"""
Channel Model — LogDistanceChannel 契约测试

运行:
    python -m simulator.test_channel_model
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
    def __init__(self, gateway_id="GW001"):
        self.id = gateway_id


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


def test_channel_model_contract():
    # 抽象基类不可替代实例化约定: 子类可用, 契约完整
    random.seed(42)
    channel = LogDistanceChannel()

    ctx = _make_context(distance=300.0, sf=7, tx_power=14.0, environment="suburban")
    result = channel.evaluate(ctx)

    # 返回类型与字段完备 (与 ChannelResult 契约一致)
    assert isinstance(result, ChannelResult)
    assert set(vars(result).keys()) == {
        "rssi",
        "snr",
        "pdr",
        "packet_received",
        "propagation_delay",
    }

    # 物理基本性质
    assert result.rssi < ctx.tx_power          # 路径损耗使 RSSI < 发射功率
    assert 0.0 <= result.pdr <= 1.0            # PDR 在 [0, 1]
    assert 0.0 < result.propagation_delay       # 单向时延 > 0

    # 纯函数: 不修改 context (ADR-001 约束)
    assert ctx.distance == 300.0
    assert ctx.spreading_factor == 7

    # 子类关系成立 (扩展点正确)
    assert isinstance(channel, ChannelModel)

    print("===== Channel Model Test =====")
    print(f"Distance : {ctx.distance} m")
    print(f"RSSI     : {result.rssi} dBm")
    print(f"SNR      : {result.snr} dB")
    print(f"PDR      : {result.pdr}")
    print(f"Received : {result.packet_received}")
    print(f"Delay    : {result.propagation_delay:.3e} s")


def test_distance_monotonic():
    """距离越远, RSSI 越低, PDR 不增 — 验证模型单调性。"""
    channel = LogDistanceChannel()
    near = channel.evaluate(_make_context(distance=100.0))
    far = channel.evaluate(_make_context(distance=5000.0))

    assert near.rssi > far.rssi
    assert near.pdr >= far.pdr

    print("===== Monotonicity Test =====")
    print(f"near RSSI={near.rssi} PDR={near.pdr}")
    print(f"far  RSSI={far.rssi} PDR={far.pdr}")


def test_link_adapter():
    """ChannelModelLinkAdapter 把新 API 桥接到旧式 calculate_link(packet, gateway)。"""
    channel = ChannelModelLinkAdapter(LogDistanceChannel())

    class _GW:
        def __init__(self):
            self.id = "GW1"
            self.x = 300.0
            self.y = 0.0

    pkt = Packet(node_id="N1", payload={}, sf=7, tx_power=14, x=0.0, y=0.0)
    out = channel.calculate_link(pkt, _GW())

    # 兼容性: 原样返回 packet, 且回填既有 + 新增字段
    assert out is pkt
    assert out.rssi is not None
    assert out.snr is not None
    assert out.gateway_id == "GW1"
    assert out.pdr is not None
    assert out.packet_received is not None
    assert out.propagation_delay > 0.0

    print("===== Adapter Bridge Test =====")
    print(f"RSSI={out.rssi} SNR={out.snr} PDR={out.pdr} "
          f"recv={out.packet_received} delay={out.propagation_delay:.3e}")


if __name__ == "__main__":
    test_channel_model_contract()
    test_distance_monotonic()
    test_link_adapter()
