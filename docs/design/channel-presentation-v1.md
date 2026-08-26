# Channel Model — Presentation & Documentation Plan v1

> **Sprint 6.4.5.0 · 设计冻结（纯文档，不改代码）**
> 本文档整理 Channel Model 子系统的可交付展示材料规划，作为 6.4.5.1（README / 图表 / 展示材料实施）的设计基线。
> **本步仅规划与冻结，不修改任何 `.py`、不修改 README、不新增图片资源、不修改测试。**

---

## 0. 状态锚点（冻结时真实状态）

| 项 | 值 |
| --- | --- |
| 分支 | `channel-model-api` |
| HEAD | `5d5c2d3 refactor(channel): freeze configuration ownership` |
| 工作树 | clean |
| 测试套件 | `pytest -q simulator` → **41 passed** |
| channel_model 模块 | `__init__.py`, `adapter.py`, `base.py`, `link_budget.py`, `log_distance.py`, `rayleigh.py`, `shadowing.py` |
| Legacy 文件 | `simulator/channel.py`, `simulator/propagation.py`, `simulator/shadowing_channel.py` 已移除（5.2.2） |

---

## 1. 当前架构图（冻结）

```text
Sensor Node
     |
     v
Packet (node_id, payload, sf, tx_power, x, y)
     |
     v
ChannelModelLinkAdapter.calculate_link(packet, gateway)
     |  - 构造 TransmissionContext (frequency/bandwidth/tx_power/environment/distance/noise_floor)
     |  - 调用 model.evaluate(context) -> ChannelResult
     |  - 回填 packet 兼容字段 + packet.channel_result 句柄
     v
ChannelModel (统一接口: evaluate(context) -> ChannelResult)
     |
     +----------------+----------------+----------------+
     |                |                |
     v                v                v
LogDistance       Shadowing         Rayleigh
(确定性基线)      (大尺度 + σ)       (小尺度快衰落)
     |                |                |
     +----------------+----------------+
                      |
                      v
                 ChannelResult v1.1
   (rssi/snr/pdr/packet_received/propagation_delay/distance/path_loss)
                      |
                      v
                 LinkBudget (解释层 / 分解层, 零侵入)
   (tx_power/frequency/bandwidth/distance/path_loss/shadowing_loss/
    fading_gain/received_power/noise_power/snr)
```

**边界不变式（6.4.x 全程守住）**：
- `ChannelModel` 信道输出契约独立；`LinkBudget` 仅作观察/分解，非新物理层。
- `config.py` 是唯一参数来源，参数流单向 `config → runtime → TransmissionContext → ChannelModel`；**模型层不 import config**。
- `adapter` / `simulation` / `ChannelResult` schema / `LinkBudget` schema 全程零改动（除 6.4.4.1 的源码注释冻结）。

---

## 2. Legacy → Current 演进图（冻结）

```text
Legacy propagation stack (Task 5.2.2 之前)
==========================================
Friis / propagation.py / channel.py / shadowing_channel.py
            |
            X  removed (commit 5efbbe7, refactor(channel): remove legacy propagation stack)
            v
ChannelModel API (统一 evaluate(context) -> ChannelResult)
            |
            v
ChannelResult v1.0 -> v1.1 (新增 distance / path_loss 自描述字段)
            |
            v
LinkBudget decomposition (解释层, 6.4.3.1)


演进收益（冻结记录）
====================
- 消除隐式耦合: 旧 stack 模型与物理公式散落、参数源不清
- 统一契约: 三模型共用 ChannelResult 输出, 消费者无需感知模型差异
- 生命周期完整: ChannelResult 经 adapter 保留为 packet.channel_result 句柄
- 可解释: LinkBudget 在不动模型的前提下显式化链路预算
- 配置边界清晰: config 唯一来源, 模型保持解耦
```

---

## 3. 模型能力矩阵（冻结）

| 模型 | Path Loss | Shadowing (大尺度) | Small-scale Fading (小尺度) |
| --- | --- | --- | --- |
| `LogDistanceChannel` | ✓ | - | - |
| `ShadowingChannel` | ✓ | Gaussian (σ = `config.SHADOW_SIGMA` = 4.0) | - |
| `RayleighChannel` | ✓ | - | Rayleigh (`h ~ CN(0,1)`, `E[|h|²] = 1`) |

**公共项（三模型共享）**：`tx_power` → `path_loss`（基于 `ENV_PATH_LOSS_EXPONENT` / 显式指数）→ `received_power` → `noise_floor` → `snr` → `pdr`。
**模型特有项**：`ShadowingChannel` 叠加 `shadowing_loss`（Gaussian）；`RayleighChannel` 叠加 `fading_gain`（小尺度快衰落，`E[fading_gain]≈1`）；`LogDistanceChannel` 两项皆为 0。

---

## 4. 验证成果摘要（冻结，引用真实门禁）

**测试套件**：`pytest -q simulator` → **41 passed**（无回归）。

| 验证维度 | 覆盖测试 | 状态 |
| --- | --- | --- |
| ChannelResult 生命周期（经 adapter 保留句柄） | `test_channel_model.py`, `test_rayleigh_channel.py`, `test_channel_model_validation.py` | ✅ |
| `distance` / `path_loss` 自描述 | `test_channel_result_statistics.py::test_distance_propagates_to_result` | ✅ |
| `path_loss` 随距离严格单调 | `test_channel_result_statistics.py::test_log_distance_path_loss_monotonic` | ✅ |
| Shadowing σ 统计收敛 ≈ `config.SHADOW_SIGMA` | `test_channel_result_statistics.py::test_shadowing_sigma_statistics` | ✅ |
| Rayleigh `E[|h|²] ≈ 1`（仅经公开 `ChannelResult`） | `test_channel_result_statistics.py::test_rayleigh_power_statistics` | ✅ |
| LinkBudget 不变量 `received_power = tx_power - path_loss + shadowing_loss + fading_gain` | `test_link_budget.py::test_core_invariant_holds_for_all_models` | ✅ |
| Adapter backward compatibility（`packet.channel_result.rssi == packet.rssi` 等） | `test_channel_result_statistics.py::test_adapter_backward_compatibility` | ✅ |
| Config ownership 解耦（模型层零 config 依赖 + 默认 fallback 策略） | `test_channel_config_ownership.py`（5 测试） | ✅ |

**统计验证纪律（防 flaky）**：Shadowing / Rayleigh 用同一 channel 实例重复 `evaluate()` N=2000 + 固定 `config.SEED`，宽松范围（如 `0.8·σ < std < 1.2·σ`、`0.8 < mean(linear power) < 1.2`），不访问模型内部随机变量。

---

## 5. README 后续规划（仅规划，6.4.5.0 不执行）

> 以下为 6.4.5.1 实施时的待办，**本步不修改 README**。

1. **架构图加入 README**
   - 将 §1 架构图（ASCII 或转 Mermaid）写入 README 的 Channel Model 章节。
   - 标注三层边界：`ChannelModel`（契约）/ `LinkBudget`（解释）/ `config`（参数源）。

2. **模型说明章节**
   - 三模型能力矩阵（§3 表格）。
   - 各自适用场景：LogDistance（确定性基线）、Shadowing（城市/郊区大尺度阴影）、Rayleigh（小尺度快衰落）。
   - 参数来源说明：所有参数经构造注入，模型层不读 config；默认值仅为 fallback。

3. **验证结果展示**
   - 引用 `pytest -q simulator → 41 passed`。
   - 列出 §4 八维验证清单，证明契约/生命周期/统计性质/兼容性全部锁定。

4. **使用示例**
   - 最小可运行片段：构造 `TransmissionContext` → `model.evaluate(context)` → 读取 `ChannelResult` / `LinkBudget.decompose(...)`。
   - 官方仿真路径：`ChannelModelLinkAdapter.calculate_link(packet, gateway)`（显式注入 `config.SHADOW_SIGMA` / `config.SEED`）。

5. **演进说明（可选）**
   - 简述 Legacy → Current 演进（§2），说明移除的 `propagation.py` / `channel.py` / `shadowing_channel.py` 与替代架构。

---

## 6. Out of Scope（6.4.5.0 不做，归后续）

- 修改 README / 代码 / 测试 / 图片资源
- YAML 化配置、CLI 参数注入、GUI 参数编辑
- Monte Carlo 框架、参数扫描、自动实验管理
- 架构图转矢量图（SVG/PNG）——保持 ASCII/Mermaid 文本，避免引入图片资源依赖

---

## 7. 提交边界

- 仅新增：`docs/design/channel-presentation-v1.md`
- 提交信息：`docs(channel): freeze presentation documentation v1`
- 门禁：`git status --short` 应仅显示 `?? docs/design/channel-presentation-v1.md`
- 完成后停在 **6.4.5.0 approval checkpoint**，不进入 README 实施（6.4.5.1）。
