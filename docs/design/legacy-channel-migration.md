# Legacy Channel Migration Design Freeze (Task 5.0)

**Sprint 6.3.4 · Task 5.0** — 设计冻结文档（不执行代码修改，仅本文件新增）

> 本文件冻结 Task 5（Legacy `LoRaChannel` / `PropagationModel` 收敛到统一
> `ChannelModel`）的迁移策略、语义差异、测试矩阵与回滚方案。
> 实现阶段（Task 5.1 / 5.2）须严格遵循本冻结，任何偏离需先回到本文件修订。

---

## 0. 状态与纪律

- **本轮只新增本设计文档**，不修改任何代码。
- 冻结核心（本轮零改动）：
  - `simulator/gateway_selector.py`
  - `simulator/channel.py`（legacy `LoRaChannel`）
  - `simulator/propagation.py`（`PropagationModel`）
  - `simulator/simulation.py`
- 关键结论（详见 §4）：**生产路径的 gateway 选择自 Task 2.2 起已走
  `ChannelModel`**，"旧世界"仅残留在测试文件与孤儿模块中。

---

## 1. Migration Scope

### 1.1 迁移对象（In Scope）
- 调用入口统一到 `ChannelModelLinkAdapter` → `ChannelModel`。
- 测试 fixture 中的 `LoRaChannel()` / `PropagationModel()` 构造点迁移。
- Task 5.2：删除 legacy 模块（`channel.py` / `propagation.py` / shim）及依赖它们的测试。

### 1.2 不包含（Out of Scope）
- `frontend` / `backend`：无任何 legacy channel 引用（已 grep 确认）。
- `packet` 格式 / `scheduler` / MAC / ADR。
- `simulation.py` 的 channel 构造（已在 Task 2.2 完成，本 Task 冻结）。

---

## 2. Legacy 行为模型冻结（不可在 5.1 中假设为纯 LogDistance）

旧链路（`channel.py` → `propagation.py`）实际物理模型：

```
PL(d) = Friis_PL0 + 10·n·log10(d/d0) + X_σ
RSSI   = tx_power - PL(d)
```

其中：

| 量 | 旧实现 | 来源 |
|---|---|---|
| `Friis_PL0` | `20·log10(4π·d0/λ)`, d0=1, f=868e6 → **≈ 31.21 dB** | `propagation.py:148-160` |
| `n`（路径损耗指数） | **3.0**（写死默认） | `propagation.py:26` |
| `X_σ`（阴影） | **N(0, 4.0)**，每次 `calculate_path_loss` 实时抽 | `propagation.py:164-170` |
| `success` | 硬阈值 `rssi >= SF_SENSITIVITY[sf]`（bool） | `channel.py:166-170` |
| `pdr` / `packet_received` / `propagation_delay` | **不设** | — |

**冻结断言：**

```
Legacy  = LogDistance(n=3.0)  +  Shadowing(σ=4.0)
```

即旧链路**不是**纯 LogDistance，而是 LogDistance(3.0) 之上叠加固定 σ=4 的
高斯阴影。任何"直接换成 `LogDistanceChannel`"的方案都会静默改变 RSSI 分布。

---

## 3. 关键一致性确认（证据化）

### 3.1 PL0 基准 —— 一致 ✅
- Legacy：`propagation.py:148-160` → `20·log10(4π·d0/λ)`
- New：`log_distance.py:60-63` → 同公式，`SPEED_OF_LIGHT=3.0e8`
  （`base.py:40`）
- ⇒ 两者 `PL0 ≈ 31.21 dB`，**无恒定偏移**。

### 3.2 接收灵敏度表 —— 逐值一致 ✅
- Legacy：`channel.py:24-38` → `{7:-123, 8:-126, 9:-129, 10:-132, 11:-134, 12:-137}`
- New：`base.py:43-50` → **完全相同**。

### 3.3 路径损耗指数 —— 需显式对齐 ⚠️
- Legacy：写死 **3.0**（`propagation.py:26`）。
- New：`ENV_PATH_LOSS_EXPONENT["suburban"] = 3.0`（`base.py:54-59`）；
  但 `simulation.py` 生产通道用 `config.PATH_LOSS_EXPONENT = 2.8`
  （`config.py:49`，Task 2.2 已冻结）。
- ⇒ 迁移默认模型用 `ShadowingChannel(environment="suburban", ...)`
  （`path_loss_exponent=None`）可**自动取到 n=3.0**，与 legacy 对齐。
  `config.PATH_LOSS_EXPONENT=2.8` 仅影响生产 `simulation.py` 通道，本 Task 不动。

---

## 4. gateway_selector 风险重新评估（关键发现）

### 4.1 鸭子类型 —— `gateway_selector.py` 零代码改动
- `gateway_selector.py` 顶部**无** `import LoRaChannel`；
  仅 `def select_best_gateway(node, gateways, channel):`
  内部 `channel.calculate_link(pkt, gw)` 并读 `pkt.rssi`
  （`gateway_selector.py:17,30,31,33`）。
- `ChannelModelLinkAdapter` 恰有同名
  `calculate_link(packet, gateway)` 方法（`adapter.py:39`），且回填
  `packet.rssi`（`adapter.py:68`）—— **签名与语义兼容**。
- ⇒ **`gateway_selector.py` 无需修改。**

### 4.2 生产路径早已迁移（Task 2.2 已解决）—— 实证
- `simulation.py:16` 已 `from simulator.channel_model import ChannelModelLinkAdapter, LogDistanceChannel`。
- `simulation.py:32-36` 构造
  `self.channel = ChannelModelLinkAdapter(LogDistanceChannel(path_loss_exponent=config.PATH_LOSS_EXPONENT, ...))`。
- `simulation.py:96` 已 `select_best_gateway(node, self.gateways, self.channel)`。
- 且 `test_simulation` 当前 PASS —— **这是"gateway_selector 已兼容 adapter"
  的运行期证据**。

> **结论：所谓"旧世界 `gateway_selector → LoRaChannel`"在生产代码中
> 已于 Task 2.2 消失。残余 legacy 引用只存在于测试与孤儿模块（见 §4.3）。**

### 4.3 残余 legacy 引用面（-clean 单仓精确核对）

| 文件 | 类型 | legacy 引用 | 备注 |
|---|---|---|---|
| `simulator/channel.py` | 生产模块 | `def LoRaChannel`（`channel.py:18`） | 仅被自身 / 测试引用 |
| `simulator/propagation.py` | 生产模块 | `def PropagationModel`（`propagation.py:20`） | **仅被 `channel.py` 消费** → 移除 channel 后成孤儿 |
| `simulator/shadowing_channel.py` | shim | `from simulator.channel_model import ShadowingChannel` | 4 行转发，无调用方 → 死 shim |
| `simulator/test_channel.py` | 测试 | `LoRaChannel()`（`test_channel.py:29`） | 测 legacy 硬阈值语义 |
| `simulator/test_gateway_selection.py` | 测试 | `LoRaChannel()` ×3（`test_gateway_selection.py:31,40,49`） | **唯一仍驱动 gateway 选择走 legacy 的入口** |
| `gateway/test_gateway.py` | 测试 | `LoRaChannel()`（`test_gateway.py:19,36`） | gateway 单元测试 |
| `simulator/test_propagation.py` | 测试 | `PropagationModel()`（`test_propagation.py:5`） | 测 legacy 传播公式 |

> 注：此前一次跨仓库 grep 把 `-clean` / 非 `-clean` / `pre-recovery-backup`
> 三仓结果混合；上表已限定在 `-clean` 单仓重新核对，为 Task 5 唯一事实源。

---

## 5. RNG 迁移策略

| | 旧 | 新 |
|---|---|---|
| 随机源 | **全局 `random`**（被 `random.seed(42)` 固定） | `ShadowingChannel(seed=42)._rng`（**私有** `Random`） |
| 抽样 | `random.gauss(0, 4.0)` | `self._rng.gauss(0, sigma)` |
| 分布 | N(0,4) | 同分布 |
| 序列 | 依赖全局 random 流状态 | 自包含、可复现、不污染全局 |

**冻结策略：不保证 bit-level RNG 兼容，只保证统计行为兼容**
（阴影分布 / 均值 / 方差一致）。

**测试调整（Case3 等距场景）：**
旧 `assert winner == "GW001"` 依赖固定 shadow 顺序，迁移后序列会变。
改为二者之一：
- **（推荐）** 新增一对**不等距**网关的确定性 case，断言精确胜者（脱离 RNG）；
- 保留一个 shadow 依赖 case，但断言 `winner in {"GW001", "GW002"}`。

---

## 6. 分阶段冻结

### Task 5.1 — Adapter Migration（gateway_selector 侧）
- **改动极小**：
  - `test_gateway_selection.py`：
    `LoRaChannel()` →
    `ChannelModelLinkAdapter(ShadowingChannel(environment="suburban", sigma=config.SHADOW_SIGMA))`
    （默认 `seed=config.SEED` 保证可复现）。
  - `gateway_selector.py`：**不改**。
- **不处理**：`channel.py` / `propagation.py` / `shadowing_channel.py`
  （留到 5.2 删除）。
- **验收**：
  - `python -m simulator.test_gateway_selection` PASS
  - `python -m simulator.test_simulation` PASS（integration）
  - `python -m simulator.test_channel_model` PASS

### Task 5.2 — Legacy Removal
- **前置条件**（全仓 grep）：
  - `grep -R "LoRaChannel"` 生产代码引用 == 0
  - `grep -R "PropagationModel"` 生产代码引用 == 0
  - 上述测试迁移完成
- **删除 / 迁移**：
  - 删 `simulator/channel.py`
  - 删 `simulator/propagation.py`（孤儿）
  - 删 `simulator/shadowing_channel.py`（死 shim）
  - 迁移或删除 `simulator/test_channel.py` / `gateway/test_gateway.py` /
    `simulator/test_propagation.py`（改为 `ChannelModel` 等价断言或移除冗余）
- **验收**：全测 PASS；`grep` 生产引用为 0。

---

## 7. 回滚策略

- 若 5.1 后出现以下任一异常：
  - RSSI 分布明显漂移
  - gateway ranking 大幅变化
  - 仿真结果异常
- **允许回滚**：`git restore` 恢复 `channel.py` + `LoRaChannel`，保留
  `channel_model/` 包；测试 fixture 回退到 `LoRaChannel()`。
- 因 5.1 **不改核心生产文件**，回滚成本 = 还原测试 fixture +（如需）
  恢复 legacy 模块，风险可控。

---

## 8. Open Decisions（已冻结）

### ✅ Option A（采纳）：默认迁移模型
```python
ChannelModelLinkAdapter(
    ShadowingChannel(environment="suburban", sigma=4.0)
)
```
- ⇒ `n=3.0`（via `ENV_PATH_LOSS_EXPONENT["suburban"]`）、`σ=4.0`，
  与 legacy 语义**最大程度一致**。
- 生产 `simulation.py` 通道仍为 `LogDistanceChannel(n=2.8)`（Task 2.2 已冻结，
  本 Task 不改动）—— 此为已知、可接受的单点偏差（见 §3.3）。

### ❌ Option B（不采纳）：`LogDistanceChannel()`
- 更干净，但 RSSI 分布偏离 legacy（无阴影、n=2.8），与"旧行为≈新实现"目标冲突。

### 语义差异记录（不影响 gateway 选择）
- `success`：legacy 硬阈值 `rssi >= sens`（bool）vs 新 `pdr` 概率采样。
- `gateway_selector` 只读 `pkt.rssi`，上述差异对选择逻辑**无影响**。

---

## 9. Regression Criteria（汇总门禁）

| 测试 | 期望 |
|---|---|
| `simulator.test_gateway_selection` | PASS（5.1 后） |
| `simulator.test_simulation` | PASS（integration，已 PASS） |
| `simulator.test_channel_model` | PASS |
| `simulator.test_channel_model_validation` | PASS |
| `grep LoRaChannel` / `grep PropagationModel`（生产） | 5.2 删除后为 0 |

---

## 10. 下一步

1. 本设计冻结文档经用户审阅。
2. 进入 **Task 5.1**：按 §6.1 迁移 `test_gateway_selection.py` fixture，
   运行 §9 门禁。
3. 5.1 验收后进入 **Task 5.2**：按 §6.2 删除 legacy 模块与孤儿测试。
