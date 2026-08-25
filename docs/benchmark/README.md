# Sprint 6.1 — Benchmark Research Suite

LoRa-IoT-Simulator 实验研究层。在 **v1.0.0 冻结核心（`simulator/` `gateway/` `backend/`）完全不修改** 的前提下，于外层 `scripts/benchmark/` 新增只读 Benchmark Harness，对仿真平台做系统化、可复现的实验验证。

> **冻结纪律**：本目录所有脚本仅 `import` 冻结后端（`backend.engine.SimulationEngine`），通过外层子类补全实验所需能力（如 `finished()`、`_build_topology()` 覆盖），**不修改任何冻结源码**。

---

## 1. 实验架构与方法论

| 项 | 说明 |
|----|------|
| Harness | `backend.engine.SimulationEngine`（只读 import） |
| 参数化入口 | `engine.configure(node_count=, area_size=, gateways=, seed=, duration=, adr_enabled=)` |
| 遥测口径 | `get_statistics()` → PDR / throughput；`get_packets()` → 逐包 `{time,event,node,sf,rssi,snr,gateway,success}` |
| 派生指标 | Average RSSI / Average SF = 全 attempt 均值；Packet Loss = 1 − PDR；Collision Rate = `success==False` attempt 占比 |
| 可复现性 | 固定 `seed=42`；距离实验额外对全局 RNG 播种以固定阴影衰落实现 |
| 依赖隔离 | `matplotlib` / `numpy` / `pandas` 单列入 `scripts/benchmark/requirements.txt`，不污染主 `requirements.txt` |
| 运行环境 | `matplotlib.use("Agg")` headless 出 PNG |

### 物理模型要点（解释实验结果的关键）
- **成功判据**（`simulator/channel.py`）：`success = (rssi >= SF_SENSITIVITY[sf])`，其中灵敏度随 SF 递减（处理增益）：`SF7=-123 … SF12=-137 dBm`。
- **碰撞判据**（`simulator/collision.py`）：同频 **且** 同 SF **且** 时间重叠 **且** `|ΔRSSI| < 6 dB` 才碰撞 → **不同 SF 彼此正交（不碰撞）**。
- **ADR**（`simulator/adr.py`）：`snr > 10 → SF−1`，`snr < 5 → SF+1`，钳制于 `[7,12]`。即 ADR 通过抬高弱链路节点的 SF，使其落入更灵敏的阈值（处理增益）并规避同-SF 碰撞。

---

## 2. Benchmark 1 — 节点规模可扩展性（Scalability）

**设计**：固定 `area_size=2000`、`seed=42`、`duration=100`、默认 ADR；扫描 `nodes ∈ {10,50,100,200,500}`。
**问题**：网络节点数增加时，交付率与吞吐如何变化？

| Nodes | PDR | Throughput | Avg RSSI (dBm) | Avg SF | Collision Rate |
|------:|----:|-----------:|----------------:|-------:|---------------:|
| 10  | 1.000 | 0.1 | −98.56 | 7.000 | 0.0000 |
| 50  | 1.000 | 0.5 | −97.44 | 7.020 | 0.0000 |
| 100 | 1.000 | 1.0 | −98.17 | 7.000 | 0.0000 |
| 200 | 1.000 | 2.0 | −99.39 | 7.005 | 0.0099 |
| 500 | 1.000 | 5.0 | −99.42 | 7.027 | 0.0234 |

**图**：`figures/scalability.png`
**结论**：在 2000 m 农场、单次上报（`PACKET_INTERVAL=300 s > duration`）负载下，PDR 恒为 1.0，吞吐随节点数线性增长（0.1→5.0 pkt/s）。节点数升至 200/500 时出现极轻微碰撞（<2.4%），但重传机制完全吸收，PDR 不受影响。说明平台在百节点级规模下链路预算充裕、无规模瓶颈。

---

## 3. Benchmark 2 — ADR 开/关对比（ADR ON/OFF）

**设计**：固定 `nodes=200`、`seed=42`、`duration=100`；扫描 `area_size ∈ {2000,3000,4000,5000,6500,8000}`，每尺度对比 ADR ON vs OFF。
**问题**：ADR 在什么条件下带来收益？

*为何用 `area_size` 作压力维度*：默认 2000 m 拓扑下，最远节点（~1581 m）RSSI ≈ −113 dBm，远高于 SF7 灵敏度 −123 dBm，ADR **完全惰性**（只能尝试把 SF7 再降，被钳制）。扩大部署面积把节点推过 SF7 灵敏度门槛，此时 LoRa 逐-SF 处理增益让 ADR 通过抬高 SF 抢救弱链路。该设计在保持随机几何不变的前提下隔离 ADR 效应——**Average RSSI 在 ON/OFF 间应完全重叠（控制变量验证）**。

| Area (m) | ADR | PDR | Packet Loss | Avg SF | Avg RSSI (dBm) |
|---------:|-----|----:|------------:|-------:|---------------:|
| 2000 | OFF | 1.000 | 0.000 | 7.000 | −99.35 |
| 2000 | ON  | 1.000 | 0.000 | 7.014 | −99.58 |
| 3000 | OFF | 1.000 | 0.000 | 7.000 | −105.93 |
| 3000 | ON  | 1.000 | 0.000 | 7.193 | −106.18 |
| 4000 | OFF | 0.995 | 0.005 | 7.000 | −113.04 |
| 4000 | ON  | 1.000 | 0.000 | 7.634 | −112.95 |
| 5000 | OFF | 0.930 | 0.070 | 7.000 | −118.90 |
| 5000 | ON  | 1.000 | 0.000 | 8.162 | −118.46 |
| 6500 | OFF | 0.715 | 0.285 | 7.000 | −124.60 |
| 6500 | ON  | 0.940 | 0.060 | 8.711 | −124.38 |
| 8000 | OFF | 0.535 | 0.465 | 7.000 | −128.32 |
| 8000 | ON  | 0.860 | 0.140 | 8.982 | −128.18 |

**图**：`figures/adr_compare.png`（2×2：PDR / Packet Loss / Avg SF / Avg RSSI）
**结论**：
> **ADR does not improve performance under strong link conditions, but provides significant reliability improvement in large-scale LoRa deployments.**

- 小尺度（≤3000 m）ADR 惰性：PDR 均为 1.0，Avg SF 几乎不变（仅 ON 略高，因个别弱链路节点开始被抬高）。
- 大尺度（≥5000 m）ADR 收益显著：6500 m 时 PDR 由 0.715 → 0.940（+22.5pp），8000 m 时由 0.535 → 0.860（+32.5pp）。
- 控制验证：每个尺度下 ON/OFF 的 **Avg RSSI 几乎重合**（如 8000 m：−128.32 vs −128.18），证明几何未变，PDR 差异纯粹来自 ADR 的 SF 自适应。
- 机制：ADR 把弱链路节点从 SF7 抬到 SF8–SF12，既获得更灵敏的接收门槛（处理增益），又因“不同 SF 正交”规避了同-SF 碰撞（碰撞率同步下降，如 8000 m：0.806 → 0.657）。

---

## 4. Benchmark 3 — 距离–PDR 链路曲线（Distance Curve）

**设计**：固定 `nodes=1`、`gateway=1`、SF=7（`ADR=OFF`）；单网关置于原点，单节点置于 `(distance, 0)`，精确控制距离。扫描 `distance ∈ {100,500,1000,1500,2000,2500,3000,4000,5000} m`。每距离对 **N=30** 个阴影衰落实现取 PDR 均值（含 ±1 std 带）。为对照，同扫描也给出 **ADR ON** 曲线。
**问题**：LoRa 链路距离增加时，可靠性如何下降？

| Distance (m) | ADR OFF — Mean PDR | ADR ON — Mean PDR |
|-------------:|-------------------:|------------------:|
| 100  | 1.000 | 1.000 |
| 500  | 1.000 | 1.000 |
| 1000 | 1.000 | 1.000 |
| 1500 | 1.000 | 1.000 |
| 2000 | 1.000 | 1.000 |
| 2500 | 1.000 | 1.000 |
| 3000 | 1.000 | 1.000 |
| 4000 | 0.700 | 1.000 |
| 5000 | 0.400 | 1.000 |

（std 带：ADR OFF 在 4000 m 为 ±0.458，5000 m 为 ±0.490，反映阴影衰落导致的过渡带；ADR ON 全程 std=0。）

**图**：`figures/distance_pdr.png`
**结论**：
- **ADR OFF（纯 SF7）**：链路预算悬崖——3000 m 内 PDR=1.0，越过 SF7 灵敏度门槛（~3.2 km）后急剧跌落到 4000 m 的 0.70、5000 m 的 0.40。这是固定扩频因子下典型的 LoRa 链路预算曲线。
- **ADR ON**：PDR 在 **全程 100–5000 m 保持 1.0**。ADR 随距离增大逐级抬高 SF（SF7→SF12 处理增益），把节点持续维持在灵敏度门槛之上，从而把有效通信距离显著延伸。
- 该结果是 **Benchmark 2 发现的最小化单节点印证**：ADR 的收益本质就是“用更高 SF 换更远的可靠链路”。

---

## 5. 综合结论（科研级要点）

1. **规模无瓶颈**：百节点级内部署下链路预算充裕，PDR 恒为 1.0，吞吐线性可扩展。
2. **ADR 是“大尺度/弱链路”专用增益**：在强链路（小农场）下惰性、无收益；在弱链路（大农场、远距离）下通过 SF 自适应把 PDR 提升最高 ~32.5pp，并同步降低碰撞率。
3. **距离–可靠性由 SF 灵敏度门槛决定**：固定 SF7 时存在 ~3.2 km 悬崖；启用 ADR 可把可靠距离延伸到 5 km 以上。
4. **可复现、只读、可审计**：全部实验未触碰冻结核心，参数与种子固定，数据落盘为 CSV + PNG，可直接进入论文/报告。

---

## 6. 运行方式

```bash
# 依赖（隔离安装，不污染主环境）
pip install -r scripts/benchmark/requirements.txt

# Benchmark 1 — 节点规模
python scripts/benchmark/run_scalability.py

# Benchmark 2 — ADR 开/关
python scripts/benchmark/run_adr_compare.py

# Benchmark 3 — 距离–PDR
python scripts/benchmark/run_distance.py
```

输出：
```
docs/benchmark/
├── scalability.csv
├── adr_compare.csv
├── distance.csv
└── figures/
    ├── scalability.png
    ├── adr_compare.png
    └── distance_pdr.png
```

---

## 7. 文件清单

| 文件 | 作用 |
|------|------|
| `scripts/benchmark/common.py` | 统一入口：`BenchmarkEngine(SimulationEngine)` 子类补 `finished()`；`run_experiment()` 聚合指标（只读后端） |
| `scripts/benchmark/run_scalability.py` | Benchmark 1 |
| `scripts/benchmark/run_adr_compare.py` | Benchmark 2（area_size 压力扫描 + ADR 对比） |
| `scripts/benchmark/run_distance.py` | Benchmark 3（`DistanceBenchmarkEngine` 覆盖 `_build_topology()` 精确布点 + ADR 对照） |
| `scripts/benchmark/requirements.txt` | 实验专用依赖 |
| `docs/benchmark/*.csv` | 原始数据 |
| `docs/benchmark/figures/*.png` | 论文级图表 |
