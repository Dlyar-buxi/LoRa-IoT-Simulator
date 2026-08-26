# ShadowingChannel — Design Freeze (Sprint 6.3.4 · Task 3.1)

冻结于 ADR-001 与 `docs/design/channel-model-api.md` 的接口契约之上。
本文件冻结 ShadowingChannel 的设计, 作为 Task 3.2 实现的唯一依据。
ShadowingChannel 是第二个 `ChannelModel` 子类, 用于实证 ADR-001 的
"Simulator 不依赖具体传播模型" 论点。

---

## 1. 物理模型

在 `LogDistanceChannel` 的对数距离路径损耗上叠加**高斯阴影衰落**:

```
PL(d) = PL(d0) + 10·n·log10(d / d0) + X_σ
X_σ ~ N(0, σ)        # 对数正态阴影, 均值 0, 标准差 σ (dB)
```

链路 (与 LogDistanceChannel 同形, 仅 RSSI 增加一项阴影):

```
LogDistance base : rssi = tx_power - PL(d)          ← 复用 LogDistanceChannel
        +
shadow           : shadow = rng.gauss(0, σ)         ← ShadowingChannel 新增
        ↓
rssi'  = rssi + shadow
snr'   = rssi' - noise_floor
pdr'   = sigmoid((rssi' - sensitivity) / 3)         ← 复用父类 _pdr_from_rssi
```

`σ = 0` 时 `shadow ≡ 0`, 链路逐字节退化为 `LogDistanceChannel`。

---

## 2. 参数冻结

| 参数 | 默认值 | 范围 / 说明 |
|---|---|---|
| `sigma` (σ) | `7.0` | 阴影标准差 (dB); 典型 4~8 dB (郊区/城区). `0` = 退化为 LogDistance |
| `seed` | `None` | `int` 时确定性复现; `None` 走系统熵 (每次运行不同实现) |
| `frequency` | `868e6` | 同 LogDistanceChannel |
| `path_loss_exponent` | `None` | 同 LogDistanceChannel (`None` 按 environment 取默认) |
| `noise_floor` | `-120.0` | 同 LogDistanceChannel |
| `reference_distance` | `1.0` | 同 LogDistanceChannel |

---

## 3. 与 LogDistanceChannel 的组合方式

**子类化 (IS-A)**:

```python
class ShadowingChannel(LogDistanceChannel):
    def evaluate(self, context) -> ChannelResult: ...
```

- 复用父类 `_path_loss()` / `_pdr_from_rssi()` 精确物理计算, **不重写路径损耗数学**。
- 仅在 RSSI 上叠加高斯阴影并重算 SNR/PDR; `TransmissionContext` / `ChannelResult`
  契约**完全不变**。
- 因此 `simulator/simulation.py` / `gateway_selector.py` / `packet.py` / `frontend`
  **零改动**即可接入第二个模型 —— 这正是 ADR-001 "Simulator 不依赖具体传播模型"
  的实证 (见 `docs/benchmark/channel-model-comparison.md`)。

---

## 4. 随机性与 seed 策略

- `ShadowingChannel` 持有私有 `random.Random(seed)`; `seed` 同时驱动:
  1. 阴影采样 `gauss(0, σ)`
  2. `packet_received` 布尔采样 `random() < pdr`
- **复现保证**: 相同 `seed` → 相同调用序列产生相同
  `RSSI` / `SNR` / `PDR` / `packet_received`; 不同 `seed` → 不同阴影实现;
  `seed=None` → 非确定 (适合生产扰动)。
- **不复用全局 `random`**: 避免污染其他模块的随机流
  (与 LogDistanceChannel 的全局 `random` 行为解耦, 利于独立复现与测试)。

---

## 5. 设计约束 (继承 ADR-001)

- `evaluate()` 纯函数式: 不修改 `Node` / `Gateway` / `context`, 无副作用。
- 仅新增文件 `simulator/shadowing_channel.py`, 不改 `channel_model.py` 既有内容。
- 所有未来模型 (Rayleigh / Urban / ML / DigitalTwin) 均为 `ChannelModel` 子类。

---

## 6. Non-goals (本轮不做)

- Rayleigh 多径快衰落 (独立模型, 后续 Sprint)
- 时变 / 移动性耦合 (本模型阴影为静态空间实现)
- 与 ADR / collision 的交互 (保持纯物理抽象)
