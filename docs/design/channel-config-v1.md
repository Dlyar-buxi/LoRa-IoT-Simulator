# Channel Model Configuration Freeze (v1)

> **Sprint 6.4.4.0 — 设计冻结（纯文档，不改代码）**
> 依赖：`channel-architecture-v1.md`(5.3)、`channel-result-v1.md`(6.4.0)、`link-budget-v1.md`(6.4.3.0)
> 提交：`docs(channel): freeze ChannelModel configuration v1`

---

## 0. 状态与纪律

- 本步仅新增本文档，**不修改 `config.py` / `channel_model/*` / `adapter.py` / `simulation.py` / 测试**。
- 调查方法：只读 `simulator/config.py` + `simulator/simulation.py` + 全仓 `config.` 引用点 grep。
- 完成于 **6.4.4.0 approval checkpoint**，下一步（6.4.4.1 实施）须单独批准。

---

## 1. 目标

把分散在 `simulator/config.py` 中的无线模型参数契约冻结为 v1 基线：

1. **参数分类** —— Radio / Propagation / Noise / Experiment 四组。
2. **参数所有权** —— `config.py` 是唯一参数来源；禁止模型模块级 `DEFAULT_*`。
3. **与 LinkBudget 对齐** —— 参数流单向 `config → runtime`，禁止运行时回写 config。
4. **默认实验配置基线** —— 记录当前值作为 v1 baseline，供后续参数扫描/论文复现锚定。
5. **Out of Scope 明确** —— 配置重构 / YAML 化 / CLI 注入 / GUI 编辑 不在此冻结范围。

---

## 2. 调查结论（只读）

### 2.1 关键发现：信道模型层零 config 依赖 ✅

grep 全仓 `config.` / `from simulator import config`：

| 命中文件 | 是否信道模型层 | 说明 |
|---|---|---|
| `simulation.py` | 否（编排层） | 注入 `PATH_LOSS_EXPONENT`/`NOISE_FLOOR`/`FREQUENCY`/`ENVIRONMENT`/`SEED` |
| `node.py` / `adr.py` / `mac.py` / `main.py` | 否 | 节点/ADR/MAC/入口 引用各自域参数 |
| `test_channel.py` / `test_gateway_selection.py` / `test_channel_result_statistics.py` / `test_link_budget.py` | 否（测试） | 显式引用 `SHADOW_SIGMA`/`SEED` |
| **`channel_model/base.py`** | **是** | **0 命中**（不 import config） |
| **`channel_model/{log_distance,shadowing,rayleigh}.py`** | **是** | **0 命中**（参数经构造函数注入） |
| **`channel_model/adapter.py`** | **是** | **0 命中**（不 import config） |

→ 信道模型层**已是配置解耦的**：所有无线参数经构造函数参数 / `TransmissionContext` 注入，模型内部不读全局 config。这是冻结的强基础。

### 2.2 已知偏差：模型内部默认硬编码（须标注红线）

尽管不读 config，模型层仍存在两处**内部默认值**，与 config 契约值可能不一致：

| 位置 | 内部默认 | config 契约值 | 风险 |
|---|---|---|---|
| `base.py` `ENV_PATH_LOSS_EXPONENT` 字典（environment → exponent 映射） | 字典字面量（urban/suburban/rural/indoor 各自 exponent） | `PATH_LOSS_EXPONENT = 2.8` | LogDistanceChannel 未显式传 `path_loss_exponent` 时走字典 **而非** config |
| `shadowing.py` `ShadowingChannel.__init__(sigma=7.0)` | `7.0` | `SHADOW_SIGMA = 4.0` | 默认 σ≠config，调用方**必须显式传 `config.SHADOW_SIGMA`** |

→ 这两处是 "模型内部硬编码" 的现存形态。冻结政策：**模型内部默认仅为 fallback，绝不可作为事实来源；调用方（simulation / 测试）必须用 config 值显式覆盖**。6.4.4.1 实施时须决定：保留（明确标注 fallback）或移除（强制调用方传参）。

---

## 3. 参数清单（Parameter Inventory）

### 3.1 无线 / 信道域参数（本冻结范围）

#### Radio Parameters —— 射频物理层

| 参数 | 值 | 行 | 单位 | 消费方 |
|---|---|---|---|---|
| `FREQUENCY` | `868e6` | 15 | Hz | `simulation.py` → LogDistanceChannel(frequency=) → context |
| `BANDWIDTH` | `125e3` | 16 | Hz | context（SF 灵敏度/空口时间） |
| `TX_POWER` | `14` | 17 | dBm | `node.py` 默认；context.tx_power |
| `DEFAULT_SF` | `7` | 19 | — | `node.py` 默认 SF；context.sf |
| `SF_RANGE` | `[7..12]` | 18 | — | `main.py` 节点 SF 抽样 |

#### Propagation Parameters —— 传播模型

| 参数 | 值 | 行 | 单位 | 消费方 |
|---|---|---|---|---|
| `ENVIRONMENT` | `"suburban"` | 24 | — | `simulation.py` → adapter(environment=) → 决定 exponent/sensitivity 查表 |
| `PATH_LOSS_REF_DIST` | `1.0` | 47 | m | 路径损耗公式参考距离 |
| `PATH_LOSS_REF` | `40.0` | 48 | dB | 参考距离处路径损耗 |
| `PATH_LOSS_EXPONENT` | `2.8` | 49 | — | `simulation.py` → LogDistanceChannel(path_loss_exponent=) |
| `SHADOW_SIGMA` | `4.0` | 50 | dB | `test_*` / `test_gateway_selection` → ShadowingChannel(sigma=) |

#### Noise Parameters —— 噪声与解调门限

| 参数 | 值 | 行 | 单位 | 消费方 |
|---|---|---|---|---|
| `NOISE_FLOOR` | `-120.0` | 23 | dBm | `simulation.py` → LogDistanceChannel(noise_floor=) → SNR |
| `COLLISION_SNR_THRESHOLD` | `6.0` | 25 | dB | `collision.py` 解调判定（相邻域） |

#### Experiment Parameters —— 可复现性

| 参数 | 值 | 行 | 单位 | 消费方 |
|---|---|---|---|---|
| `SEED` | `42` | 53 | — | `simulation.py` / `main.py` / `test_*`（三模型 `seed=`） |

### 3.2 相邻域参数（边界外，仅标注所有权，不纳入本冻结）

| 域 | 参数 | 所有权文件 |
|---|---|---|
| 农场规模 | `AREA_SIZE` / `NODE_COUNT` / `GATEWAY_COUNT` | `config.py` / `main.py` / `node.py` |
| 业务周期 | `PACKET_INTERVAL` | `node.py` |
| MAC / 重传 | `MAX_RETRY` / `BACKOFF_MIN` / `BACKOFF_MAX` | `mac.py` / `simulation.py` |
| ADR | `ADR_ENABLED` / `ADR_MIN_SF` / `ADR_MAX_SF` / `ADR_HIGH_SNR` / `ADR_LOW_SNR` | `adr.py` / `simulation.py` |
| 能量 | `BATTERY_CAPACITY_MAH` / `TX_CURRENT_MA` / `RX_CURRENT_MA` / `SLEEP_CURRENT_UA` / `VOLTAGE` | `node.py` |
| 辅助函数 | `sf_to_time_on_air()` | `config.py`（被 `simulation.py` / `node.py` 调用） |

> 这些参数**不属于信道模型契约**，但共享 `config.py` 单一来源；本冻结不改动其形态。

---

## 4. 参数所有权与数据流

### 4.1 唯一来源

```
config.py  ──(唯一参数来源)──>  orchestration (simulation.py / 测试)
                                       │
                                       v  构造函数参数注入
                                  ChannelModel / TransmissionContext
                                       │
                                       v
                                  ChannelResult  ──>  LinkBudget
```

### 4.2 引用点审计表（信道域相关）

| 文件:行 | 引用参数 | 角色 |
|---|---|---|
| `simulation.py:34` | `PATH_LOSS_EXPONENT` | 注入 LogDistanceChannel |
| `simulation.py:35` | `NOISE_FLOOR` | 注入 LogDistanceChannel |
| `simulation.py:36` | `FREQUENCY` | 注入 LogDistanceChannel |
| `simulation.py:38` | `ENVIRONMENT` | 注入 adapter |
| `simulation.py:52` | `SEED` | 仿真 RNG |
| `test_channel.py:38-39` | `SHADOW_SIGMA` / `SEED` | 构造 ShadowingChannel |
| `test_gateway_selection.py:26-27` | `SHADOW_SIGMA` / `SEED` | 同上 |
| `test_channel_result_statistics.py:77,88,101` | `SHADOW_SIGMA` / `SEED` | 统计测试 |
| `test_link_budget.py:55,75,98-99` | `SHADOW_SIGMA` / `SEED` | 预算测试 |

### 4.3 红线

- ❌ 禁止在 `channel_model/*` 内新增模块级 `DEFAULT_SIGMA` / `DEFAULT_FREQ` / `DEFAULT_NOISE` 等。
- ❌ 禁止运行时（simulation / 模型 / 测试）回写 / 修改 `config.*`。
- ❌ 禁止把 config 常量复制到模型模块作为"本地副本"。
- ✅ 参数必须经构造函数参数或 `TransmissionContext` 注入（当前已实现）。

---

## 5. 与 LinkBudget 对齐

参数流严格单向，与 §4 一致，并在 `ChannelResult → LinkBudget` 末端保持只读解释：

```
config ──> TransmissionContext ──> ChannelModel.evaluate()
                                         │
                                         v
                                   ChannelResult (rssi/snr/path_loss/distance/...)
                                         │
                                         v  (decompose, 只读消费)
                                   LinkBudgetResult (tx_power/path_loss/shadowing_loss/...)
```

- `LinkBudgetResult` 的字段（tx_power/frequency/...）**全部来自 context + ChannelResult**，不新增参数来源。
- `config` 不为 LinkBudget 引入第二套参数；LinkBudget 仅做物理分解与自描述。

---

## 6. 默认实验配置基线（v1 baseline）

冻结当前值作为 **v1 实验 baseline**（复现锚点）：

| 参数 | v1 baseline | 备注 |
|---|---|---|
| `FREQUENCY` | 868 MHz | 欧洲 ISM |
| `BANDWIDTH` | 125 kHz | 典型 LoRa |
| `TX_POWER` | 14 dBm | 范围 2~20 |
| `DEFAULT_SF` | 7 | 近距离高速 |
| `ENVIRONMENT` | `"suburban"` | 默认传播环境 |
| `PATH_LOSS_REF_DIST` | 1.0 m | — |
| `PATH_LOSS_REF` | 40.0 dB | — |
| `PATH_LOSS_EXPONENT` | 2.8 | 自由空间=2.0 |
| `SHADOW_SIGMA` | 4.0 dB | 对数正态 σ |
| `NOISE_FLOOR` | -120.0 dBm | — |
| `COLLISION_SNR_THRESHOLD` | 6.0 dB | 解调门限 |
| `SEED` | 42 | 可复现 |

> 后续若做参数扫描（6.4.x 之后），须以本 baseline 为对照、不得静默改默认值。

---

## 7. 待决项（供 6.4.4.1 决策，非本步修改）

1. **模型内部默认处理**：`base.py: ENV_PATH_LOSS_EXPONENT` 字典 与 `ShadowingChannel(sigma=7.0)` 默认，选择
   - (a) 保留为明确标注的 fallback（调用方必须传 config），或
   - (b) 移除默认、强制调用方传参（更安全但破坏现有未传参的调用点）。
2. **`ENVIRONMENT` 与 `PATH_LOSS_EXPONENT` 关系**：当前 `ENVIRONMENT` 经 adapter 查表影响 exponent/sensitivity，而 `simulation.py` 又显式传 `PATH_LOSS_EXPONENT`。二者是否应统一为单一来源（environment 查表优先 / 显式参数优先）？待定。
3. **config 类型契约**：v1 仅冻结值，未冻结类型/单位注解；后续可考虑 dataclass / TypedDict 承载。

---

## 8. Out of Scope（本冻结不包含）

- 配置重构（拆分 wireless / network / experiment 子模块）
- YAML / TOML / JSON 化配置
- CLI 参数注入（`--seed` / `--sf`）
- GUI 参数编辑
- 自动实验管理 / 参数扫描框架
- 改动任何参数当前数值

这些归属 6.4.4.x 后续 / 6.4.5 / 更远版本。

---

## 9. 提交边界

- 仅新增：`docs/design/channel-config-v1.md`
- 独立 commit：`docs(channel): freeze ChannelModel configuration v1`
- 不触碰任何 `.py`、不改动参数值、不引入运行代码。
