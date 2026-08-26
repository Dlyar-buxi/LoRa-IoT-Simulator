# RayleighChannel — Design Freeze (Sprint 6.3.4 · Task 4)

冻结于 ADR-001 与 `docs/design/channel-model-api.md` 的接口契约之上。
本文件冻结 `RayleighChannel` 的设计, 作为 Task 4 实现的唯一依据。

`RayleighChannel` 是第三个 `ChannelModel` 子类, 用于进一步实证 ADR-001 的
"Simulator 不依赖具体传播模型" 论点 —— 接入第三个模型仍只新增 1 个实现文件 +
1 个测试 + 2 个文档, 仿真引擎 / 网关选择 / 包结构零改动。

---

## 1. 物理模型

Rayleigh 衰落刻画**小尺度 (small-scale) 多径快衰落**: 接收端在无视距 (NLOS)
成分的多径环境中, 接收包络服从 Rayleigh 分布。这与 Shadowing 的**大尺度 (large-scale)
慢衰落**物理意义不同 —— 因此本模型**不继承 `LogDistanceChannel` 的随机项**,
而是作为独立的 `ChannelModel` 子类, 仅复用 `LogDistanceChannel` 的**确定性路径损耗**数学
(组合优于继承)。

链路:

```
LogDistance base : PL(d) = PL(d0) + 10·n·log10(d/d0)        ← 复用 LogDistanceChannel
        +
Rayleigh fading  : h ~ CN(0, 1)  (零均值圆对称复高斯)
                   |h|^2 ~ Exp(1)  (平均功率增益 = 1, 即 0 dB)
                   fading_dB = 10·log10(|h|^2)
        ↓
rssi  = tx_power - PL(d) + fading_dB
snr   = rssi - noise_floor
pdr   = sigmoid((rssi - sensitivity) / 3)                    ← 复用父类 _pdr_from_rssi
```

采样实现 (等价且高效, 单随机抽样):

```
u   = rng.random()                        # U ~ Uniform(0, 1)
|h|^2 = -ln(u)                            # Exp(1), 均值 1 (平均功率不变)
fading_dB = 10·log10(|h|^2)
```

> 数学等价性: 若 X, Y ~ N(0, 0.5) 独立, 则 X²+Y² ~ Exp(1); 而 -ln(U) ~ Exp(1)。
> 故 `|h|^2 = -ln(U)` 与 `|h| = sqrt(X²+Y²)` 抽样统计一致, 包络 |h| ~ Rayleigh(σ=1/√2)。

---

## 2. 参数冻结

| 参数 | 默认值 | 范围 / 说明 |
|---|---|---|
| `frequency` | `868e6` | 载波频率 (Hz), EU868 默认 |
| `path_loss_exponent` | `None` | 同 LogDistanceChannel (`None` 按 environment 取默认 n) |
| `noise_floor` | `-120.0` | 同 LogDistanceChannel (dBm) |
| `reference_distance` | `1.0` | 同 LogDistanceChannel (m) |
| `seed` | `None` | `int` 时确定性复现; `None` 走系统熵 (每次运行不同) |

**为什么没有 `sigma` 参数 (对比 Shadowing):**

Shadowing 的 `sigma` 是叠加在 RSSI 上的**对数正态随机偏移**, `sigma=0` 可逐字节退化。
Rayleigh 衰落是**零均值归一化**的 (`h ~ CN(0,1)` 已固定归一化), 不存在"关闭衰落"的
退化开关 —— 其"退化"等价于对快衰落取**统计平均**: 平均线性接收功率 = 无衰落基线
(见 §4 一致性测试)。强行加 `sigma` 缩放会破坏 CN(0,1) 归一化, 违背物理, 故不保留。

---

## 3. 与 LogDistanceChannel 的组合方式

**组合 (HAS-A), 非继承 (IS-A):**

```python
class RayleighChannel(ChannelModel):
    def __init__(self, frequency=868e6, path_loss_exponent=None,
                 noise_floor=-120.0, reference_distance=1.0, seed=None):
        # 仅复用 LogDistanceChannel 的 *确定性* 路径损耗数学 (DRY, 不继承其随机项)
        self._base = LogDistanceChannel(
            frequency, path_loss_exponent, noise_floor, reference_distance)
        self.noise_floor = noise_floor
        self.seed = seed
        # 私有 RNG: 独占驱动快衰落抽样与 packet_received 采样, 不污染全局 random
        self._rng = random.Random(seed)
```

- `RayleighChannel` 是 `ChannelModel` 子类 (满足 ADR-001 扩展点约定), 同时 `isinstance(rayleigh, LogDistanceChannel)` 为 `False` —— 二者在类型上**平行**, 物理上**独立**。
- 随机性完全自有: `fading` 抽样与 `packet_received` 采样均来自 `self._rng`, 与 `LogDistanceChannel` 的全局 `random` 行为解耦, 利于独立复现与测试。
- `TransmissionContext` / `ChannelResult` 契约**完全不变** → `simulation.py` / `gateway_selector.py` / `packet.py` / `frontend` **零改动**即可接入第三个模型。

---

## 4. 随机性与 seed 策略

- `RayleighChannel` 持有私有 `random.Random(seed)`; `seed` 同时驱动:
  1. 快衰落抽样 `|h|^2 = -ln(U)`, `U ~ Uniform(0,1)`
  2. `packet_received` 布尔采样 `random() < pdr`
- **复现保证**: 相同 `seed` → 相同调用序列产生相同 `RSSI`/`SNR`/`PDR`/`packet_received`; 不同 `seed` → 不同快衰落实现; `seed=None` → 非确定 (适合生产扰动)。
- **平均功率守恒 (关键性质)**: `E[|h|^2] = 1` ⇒ 平均*线性*接收功率 = 无衰落基线。
  注意: 因 dB 域非线性, **RSSI 的算术均值会下偏约 -2.5 dB** (Jensen 不等式, 非 bug)。
  一致性测试验证的是 `mean(10^(RSSI/10)) ≈ 10^(baseline_RSSI/10)`, 而非 dB 均值相等。

---

## 5. 验证套件 (Monte Carlo, Task 4.4)

`simulator/test_rayleigh_channel.py` 覆盖:

1. **seed 可复现**: 相同 seed → 50 次 evaluate 序列的 `rssi/snr/pdr/packet_received` 逐字节一致; 不同 seed → 不一致。
2. **衰落分布符合 Rayleigh**: 5000 样本, 收集 `|h|^2 = -ln(U)`:
   - 均值 ≈ 1.0 (容差 5%);
   - 经验 CDF 与理论 `Exp(1)` 分位数 (p∈{0.25,0.5,0.75,0.9}) 对比, 误差 < 8%;
   - 包络 `|h| = sqrt(|h|^2)` 经验 CDF 与理论 `Rayleigh(σ=1/√2)` (`F(r)=1-exp(-r²)`) 对比。
3. **平均功率守恒 (Rayleigh 版"退化"测试)**: 20000 样本, `mean(10^(RSSI/10))` 与 LogDistance 基线线性功率偏差 < 5%。
4. **Monte Carlo benchmark**: 固定 seed, 5000 样本批量采样, 在若干距离点统计覆盖概率 (RSSI > 灵敏度 占比) 与平均 PDR, 与 `LogDistanceChannel` / `ShadowingChannel(σ=7)` 量化对比, 打印对照表。
5. **经 Adapter 接入 (ADR-001 实证)**: 用 `ChannelModelLinkAdapter(RayleighChannel(seed=...))` 跑一次链路, 验证 `simulation.py` 调用点零改动即可接入第三个模型。

---

## 6. 设计约束 (继承 ADR-001)

- `evaluate()` 纯函数式: 不修改 `Node` / `Gateway` / `context`, 无副作用。
- 仅新增文件 `simulator/channel_model/rayleigh.py` + 测试 + 文档, **不修改任何冻结核心**:
  `simulation.py` / `gateway_selector.py` / `packet.py` / `config.py` / legacy `channel.py` (LoRaChannel)。
- `RayleighChannel` 经 `channel_model/__init__.py` 重导出, 调用点 `from simulator.channel_model import RayleighChannel` 零改动接入。

---

## 7. 与 Shadowing / LogDistance 的尺度对比

| 模型 | 尺度 | 衰落类型 | `sigma=0` 退化 | 与 LogDistance 关系 |
|---|---|---|---|---|
| `LogDistanceChannel` | 平均路径损耗 | 无随机 | — | 基线 |
| `ShadowingChannel` | 大尺度 | 慢衰落 (对数正态阴影) | ✅ 逐字节等价 | IS-A 子类 |
| `RayleighChannel` | 小尺度 | 快衰落 (多径 Rayleigh) | ❌ (零均值归一化, 无开关) | HAS-A 组合 (平行) |

> 物理补充: 完整真实信道 = 大尺度路径损耗 (LogDistance) + 大尺度阴影 (Shadowing) +
> 小尺度多径 (Rayleigh)。三者各自是独立 `ChannelModel` 子类, 可按场景组合/选择,
> 调用方无需改动。本轮仅实现独立的 `RayleighChannel`; 组合模型留待后续 Sprint。

---

## 8. Non-goals (本轮不做)

- Rician 衰落 (带视距分量, 需 K-factor) — 独立模型, 后续 Sprint。
- 时变 / 移动性耦合 (本模型快衰落为每包独立抽样, 不含时间相关性 / Jakes 谱)。
- 与 Shadowing 的显式组合模型 (见 §7, 留待后续)。
- 触碰 legacy `LoRaChannel` (Task 5 范围)。
