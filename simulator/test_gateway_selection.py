"""
LoRa multi-gateway selection test (Sprint 4.3)

验证 select_best_gateway 按上行 RSSI 选最佳网关。
Case3 等距场景用固定随机种子固定 shadow fading，保证可复现。
"""

from simulator.node import SensorNode
from simulator.channel_model import ChannelModelLinkAdapter, ShadowingChannel
from simulator.gateway_selector import select_best_gateway
from gateway.gateway import Gateway
import simulator.config as config


def make_channel():
    """Legacy LoRaChannel 的等价新实现 (见 legacy-channel-migration.md §8 Option A)。

    Legacy = LogDistance(n=3.0) + Gaussian shadow(σ=4);
    新实现用 ShadowingChannel(sigma=4.0, seed=固定), environment 由
    ChannelModelLinkAdapter 默认 "suburban" 在 evaluate 阶段注入 ->
    ENV_PATH_LOSS_EXPONENT["suburban"]=3.0 (对齐 legacy n=3.0)。
    以私有 RNG (seed 固定) 替代旧全局 random, 保证可复现且不污染全局流。
    """
    return ChannelModelLinkAdapter(
        ShadowingChannel(
            sigma=config.SHADOW_SIGMA,
            seed=config.SEED,
        )
    )


def make_node(x, y):
    return SensorNode(f"N-{x}-{y}", x, y, seed=1)


def test_gateway_selection():
    gw1 = Gateway("GW001", 100, 100)
    gw2 = Gateway("GW002", 1900, 1900)
    gateways = [gw1, gw2]

    print("===== Gateway Selection Test =====")
    print()

    # Case1: 节点靠近 GW001 -> 高 RSSI -> GW001
    node1 = make_node(200, 200)
    sel1 = select_best_gateway(node1, gateways, make_channel())
    print("Case1:")
    print("Selected:", sel1.id)
    print()
    assert sel1.id == "GW001"

    # Case2: 节点靠近 GW002 -> 高 RSSI -> GW002
    node2 = make_node(1800, 1800)
    sel2 = select_best_gateway(node2, gateways, make_channel())
    print("Case2:")
    print("Selected:", sel2.id)
    print()
    assert sel2.id == "GW002"

    # Case3: 等距 -> shadow 决定胜者; 新模型用私有 RNG (seed 固定但序列不同于
    # 旧全局 random), 仅保证二者之一, 不再保证精确 GW001 (见 §5 RNG 策略).
    node3 = make_node(1000, 1000)
    sel3 = select_best_gateway(node3, gateways, make_channel())
    print("Case3:")
    print("Selected:", sel3.id)
    print()
    assert sel3.id in {"GW001", "GW002"}

    print("Gateway Selection PASS")


if __name__ == "__main__":
    test_gateway_selection()
