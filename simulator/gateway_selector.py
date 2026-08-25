"""
LoRa multi-gateway selection (network layer)

Sprint 4.3: 根据上行 RSSI 为节点选择最佳网关。

职责边界（与 PHY / MAC / 碰撞解耦）：
- 不管理 MAC
- 不修改 Packet
- 不处理碰撞
- 只负责网关选择

实现：对每个网关用节点的临时包调用 channel.calculate_link 取 rssi，
选 rssi 最大者。PHY 公式的唯一来源仍是 channel.py，此处不复制路径损耗模型。
"""


def select_best_gateway(node, gateways, channel):
    """扫描所有网关，返回上行 RSSI 最高的网关对象。

    与真实 LoRaWAN 网络层行为一致：节点按链路质量（RSSI）选择最佳网关。
    始终取 max(rssi)，不对等距场景做特殊规则。
    """
    if not gateways:
        return None

    best = None
    best_rssi = None
    for gw in gateways:
        pkt = node.create_packet()        # 临时包，仅用于扫描 RSSI
        channel.calculate_link(pkt, gw)
        if best is None or pkt.rssi > best_rssi:
            best = gw
            best_rssi = pkt.rssi
    return best
