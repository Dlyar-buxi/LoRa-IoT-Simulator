# Channel Model Comparison — Benchmark (Sprint 6.3.4 · Task 3.4)

对比已实现的 `ChannelModel` 子类, 验证 ADR-001 的
"Simulator 不依赖具体传播模型, 只依赖 ChannelModel 抽象" 论点。

---

## 1. 模型矩阵

| 模型 | 确定性 | 随机性 | 典型 use case | 状态 |
|---|---|---|---|---|
| `LogDistanceChannel` | ✅ (同输入同输出) | ❌ | baseline / 快速仿真 | ✅ 已实现 (v0.1) |
| `ShadowingChannel` | seed 固定时 ✅ | ✅ (高斯阴影 X_σ) | realistic IoT / 城区覆盖 | ✅ 已实现 (Task 3) |
| `RayleighChannel` | seed 固定时 ✅ | ✅ (多径快衰落 h~CN(0,1)) | 移动 / 密集多径 | ✅ 已实现 (Task 4) |
| `UrbanChannel` | - | - | 城市建筑遮挡 | 🔜 |
| `MLChannel` | - | - | 数据驱动建模 | 🔜 |
| `DigitalTwinChannel` | - | - | 孪生反馈闭环 | 🔜 |

---

## 2. 接入成本验证 (关键结论)

新增 `ShadowingChannel` (Task 3) 与 `RayleighChannel` (Task 4) 后, 调用方迁移成本:

| 文件 | 是否改动 | 说明 |
|---|---|---|
| `simulator/channel_model/` (包) | ❌ | Task 2.4 重构后既有内容未动, 仅新增独立模块 |
| `simulator/channel_model/shadowing.py` | ➕ 新增 | Shadowing 实现 (Task 3) |
| `simulator/shadowing_channel.py` | ➕ 新增 | 转发 shim (向后兼容旧导入) |
| `simulator/test_shadowing_channel.py` | ➕ 新增 | 验证套件 |
| `simulator/channel_model/rayleigh.py` | ➕ 新增 | Task 4 唯一新增实现文件 (`ChannelModel` 子类, 组合复用路径损耗) |
| `simulator/test_rayleigh_channel.py` | ➕ 新增 | Monte Carlo 验证套件 |
| `simulator/simulation.py` | ❌ | 经 `ChannelModelLinkAdapter` 不变 |
| `simulator/gateway_selector.py` | ❌ | 仍走 `LoRaChannel` / Adapter, 零改动 |
| `simulator/packet.py` | ❌ | 契约不变 |
| `frontend` / `backend` | ❌ | 无感知 |

> **结论**: 每新增一个真实物理模型, 仅新增 1 个实现文件 + 1 个测试 + 2 个文档,
> 仿真引擎 / 网关选择 / 包结构 / 前端**零改动**。
> 继 Shadowing 后, Rayleigh 再次实证 ADR-001 的"可插拔物理层" —— 第三个模型接入
> 仍不改任何冻结核心。

---

## 3. Shadowing vs LogDistance (本 Sprint 实测)

- `sigma=0` 时 `ShadowingChannel` 与 `LogDistanceChannel` 的
  `rssi`/`snr`/`pdr` 逐字节等价
  (回归测试 `test_backward_compat_sigma0` 固化)。
- `seed` 固定 → 同序列同 `RSSI`
  (测试 `test_seed_reproducibility` 固化)。
- 1000 样本阴影均值≈0, 标准差≈σ
  (测试 `test_shadow_distribution` 固化)。

## 3.1 Rayleigh vs LogDistance / Shadowing (Task 4 实测)

- **类型平行**: `RayleighChannel` 是 `ChannelModel` 子类但**非** `LogDistanceChannel`
  子类 (`isinstance(rayleigh, LogDistanceChannel) == False`) —— 小尺度快衰落与大尺度
  慢衰落物理意义不同, 故采用**组合优于继承** (HAS-A) 而非 IS-A。
- **seed 复现**: 相同 seed → 50 次 evaluate 序列逐字节一致; 不同 seed 不一致
  (测试 `test_seed_reproducibility` 固化)。
- **衰落分布**: 5000 样本, 恢复的 `|h|^2 = -ln(U)` 均值≈1.0 (Exp(1)),
  经验 CDF 分位数与理论 Rayleigh/Exp(1) 误差 < 8%
  (测试 `test_fading_distribution` 固化)。
- **平均功率守恒** (Rayleigh 版"退化"): 20000 样本, 平均*线性*接收功率与无衰落基线
  偏差 < 5% (dB 均值因 Jensen 不等式下偏约 -2.5 dB, 属正常, 非 bug)。
- **Monte Carlo 对照** (N=5000, seed=99, ple=2.8, 近端 100% 覆盖, 远端分化):

  | dist(m) | LogDistance | Shadowing(σ=7) | Rayleigh |
  |---|---|---|---|
  | 3000 | cov 94.3% / PDR 0.943 | cov 88.9% / PDR 0.833 | cov 87.8% / PDR 0.794 |

  Rayleigh 在远端覆盖与 Shadowing 同量级 (均显著低于 LogDistance baseline),
  印证快衰落引入的额外链路损耗方差。

---

## 4. 下一步 (不在本 Sprint)

- **Rayleigh 定位修正**: Rayleigh 是**独立的小尺度 (small-scale) 快衰落模型**,
  与 Shadowing (大尺度慢衰落) **平行**, 而非"叠加在 Shadowing 之上"。
  完整真实信道 = 大尺度路径损耗 (LogDistance) + 大尺度阴影 (Shadowing) +
  小尺度多径 (Rayleigh); 三者各自是独立 `ChannelModel` 子类, 组合模型留待后续 Sprint。
- **Monte Carlo benchmark**: ✅ 已在 Task 4 内完成 (固定 seed 批量采样, 见 §3.1)。
- **迁移 `gateway_selector` 到 `ChannelModelLinkAdapter` (Task 5)**: 消除 legacy
  `LoRaChannel` 双世界, 收敛到单一 `ChannelModel` (见设计文档第 9 节)。
- **RicianChannel / UrbanChannel / MLChannel**: 后续 Sprint 候选。
