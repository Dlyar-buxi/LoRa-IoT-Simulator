"""
LoRa multi-gateway selection test (Sprint 4.3)

验证 select_best_gateway 按上行 RSSI 选最佳网关。
Case3 等距场景用固定随机种子固定 shadow fading，保证可复现。
"""

import random

from simulator.node import SensorNode
from simulator.channel import LoRaChannel
from simulator.gateway_selector import select_best_gateway
from gateway.gateway import Gateway


def make_node(x, y):
    return SensorNode(f"N-{x}-{y}", x, y, seed=1)


gw1 = Gateway("GW001", 100, 100)
gw2 = Gateway("GW002", 1900, 1900)
gateways = [gw1, gw2]


print("===== Gateway Selection Test =====")
print()

# Case1: 节点靠近 GW001 -> 高 RSSI -> GW001
random.seed(42)
node1 = make_node(200, 200)
sel1 = select_best_gateway(node1, gateways, LoRaChannel())
print("Case1:")
print("Selected:", sel1.id)
print()
assert sel1.id == "GW001"

# Case2: 节点靠近 GW002 -> 高 RSSI -> GW002
random.seed(42)
node2 = make_node(1800, 1800)
sel2 = select_best_gateway(node2, gateways, LoRaChannel())
print("Case2:")
print("Selected:", sel2.id)
print()
assert sel2.id == "GW002"

# Case3: 等距 -> shadow 决定，固定随机使 RSSI 较高方（GW001）确定性胜出
random.seed(1)
node3 = make_node(1000, 1000)
sel3 = select_best_gateway(node3, gateways, LoRaChannel())
print("Case3:")
print("Selected:", sel3.id)
print()
assert sel3.id == "GW001"

print("Gateway Selection PASS")
