# LinkBudget 架构冻结 v1 — Sprint 6.4.3.0

> **状态**：设计冻结（DESIGN FREEZE）。本文档为纯设计文档，**不含任何代码改动**。
> **当前基线**：`f1f662b test(channel): add ChannelResult statistical validation`（6.4.2）
> **下游实施**：`6.4.3.1`（本文档批准后的实现阶段）
> **纪律**：只读调查 → 设计冻结 → 审阅批准 → 实施 → 测试 → 独立 commit

---

## 1. 目标与动机

ChannelResult v1.1（6.4.1）已把一次链路计算的核心输出（`rssi/snr/pdr/distance/path_loss`）
保留为自描述句柄。但**这些字段只是结果，不是过程**——接收功率到底被路径损耗、阴影、
瑞利快衰落、噪声各吃了多少 dB，目前是隐式散落在三个模型 `evaluate()` 内部的。

引入 `LinkBudgetResult` 的动机：

1. **可解释性**：把 `Tx → PathLoss → (Shadowing | Rayleigh) → ReceivedPower → Noise → SNR → PDR`
   的每一步显式化为带符号的中间量，论文/展示材料可直接画链路预算图。
2. **Monte Carlo 就绪**：未来参数扫描、批量统计只需复用 `LinkBudget` 的纯分解函数，
   不必重写物理公式（见 §8 Out of Scope —— Monte Carlo 本身不在本步）。
3. **零风险**：仅做**解释/分解/记录/验证**，不改变任何物理输出数值（红线见 §6）。

---

## 2. 当前真实链路预算流（只读调查结论）

> 调查对象：`base.py` / `log_distance.py` / `shadowing.py` / `rayleigh.py` / `adapter.py` / `__init__.py`
> 所有公式与代码位置均来自上述文件，未做任何修改。

### 2.1 公共预算项（三模型共有）

| 步骤 | 公式 | 代码位置 | 参数来源 |
|---|---|---|---|
| 波长 | `λ = SPEED_OF_LIGHT / frequency` | `log_distance._reference_loss` | `base.SPEED_OF_LIGHT=3e8`, `context.frequency` |
| 参考损耗 | `pl0 = 20·log10(4π·d0/λ)` | `log_distance._reference_loss` | `d0 = reference_distance`（默认 1.0） |
| 路径损耗指数 | `n = path_loss_exponent or ENV_PATH_LOSS_EXPONENT[environment]` | `log_distance._exponent` | `base.ENV_PATH_LOSS_EXPONENT`（urban 3.5/suburban 3.0/rural 2.7/indoor 3.2，缺省 3.0） |
| 路径损耗 | `PL(d) = pl0 + 10·n·log10(d/d0)` | `log_distance._path_loss` | `context.distance`, 上述 n/d0/pl0 |
| 接收功率(基线) | `P_rx = tx_power − PL(d)` | `log_distance.evaluate` / `shadowing.evaluate` / `rayleigh.evaluate` | `context.tx_power` |
| 噪声功率 | `N = noise_floor` | 各模型 `evaluate` | `model.noise_floor`（默认 −120.0 = `config.NOISE_FLOOR`） |
| 信噪比 | `SNR = P_rx − N` | 各模型 `evaluate` | 上述两者 |
| 包投递率 | `PDR = 1 / (1 + e^(−(P_rx − SENS)/3))` | `log_distance._pdr_from_rssi` | `SENS = SF_SENSITIVITY[sf]`（base，`−123` 兜底），软度 3 dB |
| 传播时延 | `τ = d / SPEED_OF_LIGHT` | 各模型 `evaluate` | `context.distance` |

**公共项小结**：`tx_power, frequency, bandwidth, distance, d0, n, pl0, path_loss,
noise_floor, SPEED_OF_LIGHT, SF_SENSITIVITY, received_power, snr, pdr, propagation_delay`
在三个模型中**算法完全一致**，差异只在「是否在基线接收功率上叠加衰落项」。

### 2.2 模型特有项

| 模型 | 特有项 | 公式 | 代码位置 | 参数 |
|---|---|---|---|---|
| **LogDistanceChannel** | （无） | `P_rx = tx_power − PL(d)` | `log_distance.evaluate` | — |
| **ShadowingChannel** | `shadowing_loss` | `X_σ ~ N(0, σ)`；`P_rx += X_σ` | `shadowing.evaluate`（`self._rng.gauss(0, sigma)`） | `model.sigma`（默认 7.0；按冻结配置 `config.SHADOW_SIGMA=4.0` 构造） |
| **RayleighChannel** | `fading_gain` | `h² = −ln(U), U~Uniform(0,1)` ⇒ `h²~Exp(1)`，`E[h²]=1`；`fading_gain = 10·log10(h²)`；`P_rx += fading_gain` | `rayleigh.evaluate`（`self._rng.random()`） | 仅 seed（无 sigma） |

> **关键不变量**：`received_power = tx_power − path_loss + shadowing_loss + fading_gain`。
> 三个模型都是该式的特例：
> - LogDistance：`shadowing_loss = 0, fading_gain = 0`
> - Shadowing：`shadowing_loss ≠ 0, fading_gain = 0`
> - Rayleigh：`shadowing_loss = 0, fading_gain ≠ 0`
> 二者在任一当前模型内互斥（不会同时非零）。

### 2.3 参数来源总表

| 参数 | 来源 | 默认/配置值 |
|---|---|---|
| `tx_power` | `TransmissionContext.tx_power` ← `Packet.tx_power` ← `config.TX_POWER` | 14 dBm |
| `frequency` | `context.frequency` ← `Packet.frequency` ← `config.FREQUENCY` | 868e6 Hz |
| `bandwidth` | `context.bandwidth` ← `Packet.bandwidth` ← `config.BANDWIDTH` | 125e3 Hz |
| `distance` | `context.distance` ← adapter（节点/网关坐标 `hypot`） | — |
| `d0` | `model.reference_distance` | 1.0 m |
| `n` | `model.path_loss_exponent` 或 `ENV_PATH_LOSS_EXPONENT[env]` | 3.0（兜底） |
| `sigma` | `model.sigma`（仅 Shadowing） | 7.0（配置 4.0） |
| `noise_floor` | `model.noise_floor` | −120.0 dBm |
| `SPEED_OF_LIGHT` | `base.SPEED_OF_LIGHT` | 3e8 m/s |
| `SF_SENSITIVITY` | `base.SF_SENSITIVITY[sf]` | −123（兜底） |
| `seed` | `model.seed`（Shadowing/Rayleigh；LogDistance 用全局 `random`，确定性仅由调用方控制） | None / 42 |

---

## 3. 冻结设计：LinkBudgetResult 独立层

### 3.1 落点（已批准）

```
simulator/channel_model/link_budget.py   # 纯函数分解层（6.4.3.1 实施，本步不建）
```

职责分离（已批准）：

```
ChannelResult    = 信道输出契约（消费者/适配器/simulation 依赖，绝不改）
LinkBudgetResult = 物理链路预算解释层（一次链路的可解释中间态）
```

**红线**：禁止把 LinkBudget 字段塞入 `ChannelResult`。两者是「契约」与「解释」的分离，
`LinkBudgetResult` 是**新增类型**，不改变任何现有数据结构。

### 3.2 LinkBudgetResult 初版字段（冻结）

```python
@dataclass
class LinkBudgetResult:
    tx_power: float          # dBm，context.tx_power
    frequency: float         # Hz
    bandwidth: float         # Hz
    distance: float          # m

    path_loss: float         # dB，PL(d) = pl0 + 10·n·log10(d/d0)

    shadowing_loss: float    # dB，Gaussian N(0,σ)；LogDistance=0，Rayleigh=0
    fading_gain: float       # dB，10·log10(|h|²)，|h|²~Exp(1)，E[|h|²]=1；LogDistance=0，Shadowing=0

    received_power: float    # dBm = tx_power − path_loss + shadowing_loss + fading_gain
    noise_power: float       # dBm = noise_floor
    snr: float               # dB = received_power − noise_power
```

**说明**：
- 这些字段是「链路预算过程的可解释状态」，**不是新的 packet API**，也不进入 `Packet`。
- 刻意**不含 `propagation_delay`**：它是传播时延，不属于功率/噪声预算，留在 `ChannelResult`。
- `received_power` 与 `ChannelResult.rssi` 必须数值相等；`snr` 与 `ChannelResult.snr` 必须相等
  （见 §6 红线与 §7 不变量）。

### 3.3 与 ChannelResult 的关系

```
ChannelModel.evaluate(context)
        │
        ├─► 计算 LinkBudgetResult（纯分解，可解释）
        │        └─ 由 LinkBudgetResult 推导/校验 ChannelResult
        │
        └─► 返回 ChannelResult（消费者契约，不变）
```

6.4.3.1 的具体接线方式（构造位置/是否缓存）属于实施细节，本冻结文档不规定；
但**无论怎么接，`ChannelResult` 的数值输出必须与当前模型逐字节一致**（红线保证）。

---

## 4. 模型填充规则（冻结）

| 模型 | 填充 |
|---|---|
| **LogDistanceChannel** | 公共项全填；`shadowing_loss = 0`，`fading_gain = 0` |
| **ShadowingChannel** | = LogDistance 公共项 + `shadowing_loss`（Gaussian N(0,σ)）；`fading_gain = 0` |
| **RayleighChannel** | = LogDistance 公共项 + `fading_gain`；`shadowing_loss = 0` |

**统计约定（Rayleigh）**：`fading_gain` 的底层线性功率增益 `|h|² ~ Exp(1)`，
`E[|h|²] = 1`（平均线性功率增益守恒，0 dB 均值）；在 dB 域因 Jensen 不等式均值约 −2.5 dB
（见 `docs/design/rayleigh-channel.md` §4）。冻结文档记「`E[fading_gain]=1`」指 **`E[|h|²]=1`**，
6.4.3.1 与统计测试须按此理解，不要误判 dB 域均值。

---

## 5. 兼容性 / 迁移影响（冻结）

- **零迁移债**：`LinkBudgetResult` 是新增类型，`ChannelResult` / `adapter.py` /
  `simulation.py` / 所有消费者**不变**。
- **现有测试**：当前 32 个 simulator 测试（含 6.4.2 的 5 个）预期全部不变、无回归。
- **新增测试**：6.4.3.1 引入 `simulator/test_link_budget_*.py`，仅验证数值等价与填充规则。

---

## 6. 红线（冻结 —— LinkBudget 只允许「解释/分解/记录/验证」）

LinkBudget **禁止**做任何会改变物理输出的事：

- ❌ 改变 `rssi` / `received_power`
- ❌ 改变 `snr`
- ❌ 改变 `pdr` / `packet_received`
- ❌ 改变随机过程、`seed`、`sigma`、环境指数 `n`、`noise_floor`、`frequency`、`bandwidth`
- ❌ 向 `ChannelResult` 增删字段
- ❌ 修改 `adapter.py` / `simulation.py` / 任何消费者

**不变量（强制）**：给定相同 `TransmissionContext` 与相同 RNG 状态，
`LinkBudgetResult.received_power == 当前模型 ChannelResult.rssi`（浮点容差内），
`snr == ChannelResult.snr`，`path_loss == ChannelResult.path_loss`。

---

## 7. 验证计划（供 6.4.3.1 实施参考，本步不执行）

对每个模型 + 固定 `seed` + 固定 `context`：

1. **数值等价**：`LinkBudgetResult.received_power ≈ ChannelResult.rssi`、
   `snr ≈ ChannelResult.snr`、`path_loss ≈ ChannelResult.path_loss`（容差 1e-6）。
2. **填充规则**：
   - LogDistance：`shadowing_loss == 0 and fading_gain == 0`
   - Shadowing：`fading_gain == 0`，`shadowing_loss` 为 Gaussian 采样
   - Rayleigh：`shadowing_loss == 0`，`fading_gain` 来自 `|h|²`
3. **统计（Rayleigh）**：`mean(10^(fading_gain/10)) ≈ 1`（宽松 0.8~1.2，N≈2000，
   固定 seed）—— 复用 6.4.2 的统计纪律，避免 flaky。
4. **独立 commit**：`feat(channel): add LinkBudget decomposition`（与本冻结文档分离）。

---

## 8. Out of Scope（明确排除，写入冻结）

6.4.3.0 **不包含**：

- ❌ Monte Carlo 框架
- ❌ 参数扫描 / 自动优化
- ❌ 配置重构
- ❌ UI / README 更新
- ❌ 修改任何既有测试的预期值

上述分别归属：`6.4.3.x`（Monte Carlo 等后续演进）、`6.4.4`（配置冻结）、`6.4.5`（展示材料）。

---

## 9. 后续路线（仅记录，不在本步）

```
6.4.3.0  LinkBudget 设计冻结        ← 本步（纯文档 + 独立 commit）
6.4.3.1  LinkBudget 实施           （按 §7 验证，独立 commit）
6.4.3.x  Monte Carlo / 参数扫描    （可选扩展）
6.4.4    配置冻结                  （模型定型后）
6.4.5    展示材料                  （架构图/模型对比/README/简历）
```
