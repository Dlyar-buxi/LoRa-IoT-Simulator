"""Step 1 入口：创建虚拟节点并验证可运行。

运行方式：
    python simulator/main.py
"""
import os
import sys

# 将项目根目录加入导入路径，使 `from simulator...` 可用
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import random

from simulator import config
from simulator.node import SensorNode


def main():
    print("=" * 52)
    print("  LoRa Smart Agriculture IoT Simulator — Step 1")
    print("=" * 52)
    print(f"  农场区域 : {config.AREA_SIZE} × {config.AREA_SIZE} m")
    print(f"  节点数量 : {config.NODE_COUNT}")
    print(f"  网关数量 : {config.GATEWAY_COUNT}")
    print(f"  默认 SF  : {config.DEFAULT_SF}  |  发射功率 : {config.TX_POWER} dBm")
    print("-" * 52)

    rng = random.Random(config.SEED)
    nodes = []
    for i in range(config.NODE_COUNT):
        x = rng.uniform(0, config.AREA_SIZE)
        y = rng.uniform(0, config.AREA_SIZE)
        node = SensorNode(
            node_id=f"Node{i + 1:03d}",
            x=x,
            y=y,
            battery=rng.uniform(80, 100),
            sf=rng.choice(config.SF_RANGE),
            tx_power=config.TX_POWER,
            seed=config.SEED + i,
        )
        nodes.append(node)

    print(f"已创建 {len(nodes)} 个虚拟节点\n")

    # 展示前 5 个节点：数据生成 + 数据包构造
    print("前 5 个节点状态示例：")
    for n in nodes[:5]:
        data = n.generate_data()
        pkt = n.create_packet()
        print(f"  [{n.node_id}] pos=({n.x:5.0f},{n.y:5.0f}) "
              f"batt={n.battery:5.1f}% sf={n.sf} "
              f"T={data['temperature']:5.1f}C "
              f"H={data['humidity']:5.1f}% "
              f"Soil={data['soil']:5.1f}%")
        assert pkt.device_id == n.node_id
        assert set(pkt.payload) == {"temperature", "humidity", "soil", "light", "co2"}

    # 简单能耗验证
    e = nodes[0].consume_energy("tx", duration_s=0.1)
    print(f"\n能量模型自测：Node001 发射 0.1s 耗电 {e:.4f} mAh，"
          f"剩余 {nodes[0].battery:.2f}%")

    print("-" * 52)
    print("Step 1 完成：虚拟节点可创建、生成数据、构造数据包、消耗电量。")


if __name__ == "__main__":
    main()
