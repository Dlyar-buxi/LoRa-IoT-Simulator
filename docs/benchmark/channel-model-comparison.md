# Channel Model Comparison — Benchmark (Sprint 6.3.4 · Task 3.4)

对比已实现的 `ChannelModel` 子类, 验证 ADR-001 的
"Simulator 不依赖具体传播模型, 只依赖 ChannelModel 抽象" 论点。

---

## 1. 模型矩阵

| 模型 | 确定性 | 随机性 | 典型 use case | 状态 |
|---|---|---|---|---|
| `LogDistanceChannel` | ✅ (同输入同输出) | ❌ | baseline / 快速仿真 | ✅ 已实现 (v0.1) |
| `ShadowingChannel` | seed 固定时 ✅ | ✅ (高斯阴影 X_σ) | realistic IoT / 城区覆盖 | ✅ 已实现 (Task 3) |
| `RayleighChannel` | ❌ | ✅ (多径快衰落) | 移动 / 密集多径 | 🔜 后续 Sprint |
| `UrbanChannel` | - | - | 城市建筑遮挡 | 🔜 |
| `MLChannel` | - | - | 数据驱动建模 | 🔜 |
| `DigitalTwinChannel` | - | - | 孪生反馈闭环 | 🔜 |

---

## 2. 接入成本验证 (关键结论)

新增 `ShadowingChannel` 后, 调用方迁移成本:

| 文件 | 是否改动 | 说明 |
|---|---|---|
| `simulator/channel_model.py` | ❌ | 既有内容未动, 仅新增独立文件 |
| `simulator/shadowing_channel.py` | ➕ 新增 | 唯一新增实现文件 |
| `simulator/test_shadowing_channel.py` | ➕ 新增 | 验证套件 |
| `simulator/simulation.py` | ❌ | 经 `ChannelModelLinkAdapter` 不变 |
| `simulator/gateway_selector.py` | ❌ | 仍走 `LoRaChannel` / Adapter, 零改动 |
| `simulator/packet.py` | ❌ | 契约不变 |
| `frontend` / `backend` | ❌ | 无感知 |

> **结论**: 增加一个真实物理模型, 仅新增 1 个实现文件 + 1 个测试 + 2 个文档,
> 仿真引擎 / 网关选择 / 包结构 / 前端**零改动**。
> ADR-001 的"可插拔物理层"被实证, 而非纸面设计。

---

## 3. Shadowing vs LogDistance (本 Sprint 实测)

- `sigma=0` 时 `ShadowingChannel` 与 `LogDistanceChannel` 的
  `rssi`/`snr`/`pdr` 逐字节等价
  (回归测试 `test_backward_compat_sigma0` 固化)。
- `seed` 固定 → 同序列同 `RSSI`
  (测试 `test_seed_reproducibility` 固化)。
- 1000 样本阴影均值≈0, 标准差≈σ
  (测试 `test_shadow_distribution` 固化)。

---

## 4. 下一步 (不在本 Sprint)

- **RayleighChannel**: 在 Shadowing 之上叠加多径瑞利快衰落
  (需 seed 复现 + 快衰落时变建模)。
- **Monte Carlo benchmark**: 固定 seed, 批量采样统计 PDR / 覆盖概率,
  与 LogDistance baseline 量化对比。
- **迁移 `gateway_selector` 到 `ChannelModelLinkAdapter`**: 消除 legacy
  `LoRaChannel` 双世界, 收敛到单一 `ChannelModel` (见设计文档第 9 节)。
