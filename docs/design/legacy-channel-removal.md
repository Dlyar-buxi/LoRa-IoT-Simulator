# Task 5.2 — Legacy Channel / Propagation Removal (Design Freeze)

> 本文件冻结 Task 5.2：删除遗留物理栈 `channel.py` / `propagation.py` / `shadowing_channel.py` shim，
> 使 `ChannelModel` 抽象成为**唯一信道入口**（ADR-001 终态）。
> 调查基于 `git grep` + 源码实读（post 5.1，`HEAD = c6a02a6`），所有结论均来自事实。

---

## 1. 删除目标

| 文件 | 内容 | 处置 |
|---|---|---|
| `simulator/channel.py` | `LoRaChannel`（legacy 链路，硬阈值 `success=rssi>=sens`） | 删（5.2.2） |
| `simulator/propagation.py` | `PropagationModel`（Friis PL0 + n·log10(d) + gauss(0,4) 阴影） | 删（5.2.2） |
| `simulator/shadowing_channel.py` | 4 行 shim：`from simulator.channel_model import ShadowingChannel` | 删（5.2.2） |

**保留**：`simulator/channel_model/`（唯一信道实现层）。

---

## 2. 当前引用面（已核实）

| 对象 | 生产代码引用 | 测试引用 | 文档 |
|---|---|---|---|
| `LoRaChannel` | **0**（引擎代码零引用，见 §3） | `gateway/test_gateway.py:6,19`（待 5.2.1 迁） | 设计文档说明性文字 |
| `PropagationModel` | 仅 `channel.py:14`（被删文件内部） | `test_propagation.py:1,5`（待 5.2.1 删） | 设计文档说明性文字 |
| `shadowing_channel` shim | 0 | `test_shadowing_channel.py:11`（待 5.2.2 改 import） | 设计文档说明性文字 |

**闭环关系**：`channel.py` 导入 `propagation.py`；`propagation.py` 仅依赖 `math`/`random`。
二者互为遗留孤岛，删除后**不波及其它任何生产模块**。

---

## 3. 生产引擎代码零引用（关键安全论证）

通过实读确认以下文件**不含** `LoRaChannel` / `PropagationModel` / `simulator.channel` / `simulator.propagation`：

- `simulator/simulation.py` —— 早已用 `ChannelModelLinkAdapter(LogDistanceChannel(...))`（Task 2.2）
- `simulator/gateway_selector.py` —— 鸭子类型，顶部无 `import LoRaChannel`，只调 `channel.calculate_link()`
- `gateway/gateway.py` —— `receive()` 仅读 `packet.success`，不感知具体模型
- `simulator/packet.py` / `simulator/config.py` —— 仅提供字段/常量
- `simulator/__init__.py` / `gateway/__init__.py` —— 仅文档字符串，无再导出

> **结论**：5.2 的删除爆炸半径 = 0（对生产引擎）。这是首次真正删除遗留文件，
> 但风险已被调查收敛到纯测试层。

---

## 4. 语义对齐（删除后即可视为等价）

Legacy 物理栈实测 = `Friis PL0 ≈ 31.21 dB` + `10·n·log10(d)`（**n=3.0 写死**）+ `gauss(0, 4.0)` 阴影。
新架构对应物 = `ChannelModelLinkAdapter(ShadowingChannel(sigma=4.0))`，其中：

- `ShadowingChannel` 未传 `path_loss_exponent` 时按 `environment` 查 `ENV_PATH_LOSS_EXPONENT`；
  adapter 默认 `environment="suburban"` → **n=3.0**（对齐 legacy）。
- `sigma=config.SHADOW_SIGMA=4.0`（对齐 legacy 阴影）。
- `SF_SENSITIVITY` 表与 legacy `LoRaChannel.SF_SENSITIVITY` **逐值相同**（SF7:-123 … SF12:-137）。
- `SPEED_OF_LIGHT` 驱动的 Friis PL0 与 legacy `PropagationModel.calculate_reference_loss` 一致（≈31.21 dB）。

> **差异（必须文档化，非回归）**：
> - legacy `success = rssi >= sensitivity`（硬阈值 bool）；
>   新 `success = packet_received`（PDR 概率采样 bool）。
> - legacy 用全局 `random`；新用模型私有 `Random(seed)`。
> - 因此不保证 bit-level 复现，只保证**统计行为等价**（见 §5.1 断言变更）。

---

## 5. Task 5.2.1 — 测试迁移（先于删除）

### 5.1 `gateway/test_gateway.py`

- import 替换：
  ```python
  from simulator.channel import LoRaChannel          # 删
  from simulator import config                        # 加
  from simulator.channel_model import (               # 加
      ChannelModelLinkAdapter, ShadowingChannel)
  ```
- fixture 替换：`channel = LoRaChannel()` →
  `channel = ChannelModelLinkAdapter(ShadowingChannel(sigma=config.SHADOW_SIGMA, seed=config.SEED))`
- 保留 `random.seed(42)`（仅用于节点坐标确定性放置）；接收采样走 adapter 私有 RNG（seed 固定）→ 整体确定性。
- **断言变更（关键）**：legacy `assert stats["received"] == NODE_COUNT`（100%）依赖硬阈值，
  边缘节点失败概率极低而侥幸全收。新模型 `success` 为 PDR 概率采样，即便 PDR≈0.98 也会
  有少数随机失败 → 该断言会 flaky。**改为统计型**：
  ```python
  assert stats["received"] >= int(NODE_COUNT * 0.95)   # received_rate >= 95%
  ```
  预期 rate≈0.99（seed 固定下确定性通过），0.95 为安全余量。
- `gateway/gateway.py` **不改动**（只读 `packet.success`）。

### 5.2 `test_propagation.py` → Option A（删除 + 替代）

- **删除** `simulator/test_propagation.py`：它测 `PropagationModel.calculate_distance` / `calculate_path_loss`
  专属内部 API，新架构无此对象（路径损耗已内聚进各 `ChannelModel.evaluate`）。
- **新增** `simulator/test_channel_model_path_loss.py`，统一验证三大模型的路径损耗物理规律：
  1. **PL0 一致性**：`LogDistance` / `Shadowing` / `Rayleigh` 在 d=1m 的 `_path_loss` ≈ Friis ≈ 31.21 dB（用 `SPEED_OF_LIGHT`）。
  2. **n 敏感性**：显式 `path_loss_exponent` 改变输出；`environment="suburban"` 查表得 3.0。
  3. **阴影不改变均值路径损耗**：`ShadowingChannel(sigma>0)` 对 RSSI 叠加零均值阴影，平均 PL 与 `LogDistance` 一致（Monte Carlo 验证均值偏差 <1%）。
  4. **瑞利快衰落不改变路径损耗**：`RayleighChannel` 的快衰落只作用在 RSSI 分布，平均 PL 与基线一致。
  5. **距离单调性**：距离↑ ⇒ 路径损耗↑（物理规律守住）。
- 不重复 `test_shadowing_channel` 的逐字节退化测试，聚焦"路径损耗层"的统一契约。

---

## 6. Task 5.2.2 — 删除提交

执行顺序（同一 commit）：

1. `git rm simulator/channel.py simulator/propagation.py simulator/shadowing_channel.py`
2. **改 import**：`simulator/test_shadowing_channel.py:11`
   `from simulator.shadowing_channel import ShadowingChannel`
   → `from simulator.channel_model import ShadowingChannel`
   （否则删 shim 后该测试 `ModuleNotFoundError`）
3. （可选）清理 `channel_model/__init__.py:10`、`channel_model/base.py:25` 中"legacy channel.py 同名冲突"的过时注释。
4. 验证：
   - `python -m compileall simulator`（无 import 错误）
   - `python -m simulator.test_channel_model_path_loss`（新增测试 PASS）
   - `python -m simulator.test_shadowing_channel`（import 修复后 PASS）
   - `python -m simulator.test_gateway_selection` / `test_channel` / `test_gateway_network`
   - `git grep LoRaChannel` / `git grep PropagationModel` → **仅剩 docs + git history**
5. 提交：`remove(channel): retire legacy LoRaChannel propagation stack`

---

## 7. Task 5.3 — Architecture Lock（5.2.2 之后）

新增 `docs/design/channel-architecture-v1.md`，冻结最终架构图：

```
Node ─▶ Packet ─▶ ChannelModelLinkAdapter ─▶ ChannelModel
                                              │
                       +──────────┬──────────┼──────────┐
                       │          │          │          │
                  LogDistance  Shadowing  Rayleigh   (未来 Urban/ML)
                  (大尺度)    (大尺度随机) (小尺度快衰落)
```

对比初态 `LoRaChannel → PropagationModel`，确认 ADR-001 收敛、单一信道入口达成。
可并入 5.2.2 commit 或独立提交（执行时定）。

---

## 8. 删除前置条件（gate）

进入 5.2.2 删除前，必须满足：

```
git grep -n "LoRaChannel"      # 生产代码引用 == 0（仅 channel.py 定义本身）
git grep -n "PropagationModel" # 生产代码引用 == 0（仅 propagation.py 定义本身）
```

即：5.2.1 完成（`gateway/test_gateway.py` 已迁移、`test_propagation.py` 已删）之后，
全仓除 legacy 定义文件自身外，无任何代码引用遗留符号。

---

## 9. 回滚方案

- **5.2.1（仅测试）**：`git restore gateway/test_gateway.py simulator/test_propagation.py` 回到 legacy fixture。
- **5.2.2（删文件）**：`git restore simulator/channel.py simulator/propagation.py simulator/shadowing_channel.py simulator/test_shadowing_channel.py` 从父提交恢复；引擎代码无需改动。

---

## 10. 风险与注意事项

- **最高风险 Task**：首次真正删除遗留核心相邻文件。但调查证明生产引擎零引用，爆炸半径=0。
- **唯一隐蔽耦合点**：删 `shadowing_channel.py` shim 会断 `test_shadowing_channel.py:11` 的 import
  → 必须在 5.2.2 同一 commit 内改该 import（已在 §6 列出）。
- **语义非等价声明**：新 `success` 为概率采样，legacy 100%-received 断言被统计断言替代，
  属**设计性变更**而非回归，已在本文件 §4 与 §5.1 固化。
- 纪律延续：不修改 `simulation.py` / `gateway_selector.py` / `gateway/gateway.py` / `packet.py` / `config.py`。
