# ChannelModel Architecture v1 — Freeze

- **Status**: FROZEN (2026-08-26, Sprint 6.3.4)
- **Scope**: `simulator/channel_model/*` + `ChannelModelLinkAdapter`
- **Frozen core (untouched by channel work)**: `simulation.py`, `gateway_selector.py`, `packet.py`, `config.py`

---

## 1. Architecture Layering

```text
SensorNode
    |
    v
Packet
    |
    v
ChannelModelLinkAdapter
    |
    v
ChannelModel
    |
    +----------------------+
    |          |           |
    v          v           v
LogDistance  Shadowing   Rayleigh
```

**Data flow**: `SensorNode → Packet → ChannelModelLinkAdapter → ChannelModel → {LogDistance | Shadowing | Rayleigh}`

**Contracts (frozen)**:

- `ChannelModel.evaluate(context: TransmissionContext) -> ChannelResult`
  - `TransmissionContext` injects `environment` / `frequency` / `noise_floor` / `reference_distance`.
  - Each model is responsible for computing path loss + fading + link quality from the context.
- `ChannelModelLinkAdapter.calculate_link(packet, gateway) -> packet`
  - Legacy-compatible entry point. Backfills `rssi` / `snr` / `success` / `distance` / `pdr` / `packet_received` / `propagation_delay` onto the packet.
  - Bridges the old `PropagationModel.calculate_path_loss(packet, gateway)` call shape used by `simulation` and `gateway_selector`.
- `simulation` / `gateway_selector` depend **only** on the Adapter's `calculate_link(packet, gateway)` shape and must **never** import or reference a concrete model (`LogDistanceChannel` / `ShadowingChannel` / `RayleighChannel`).

---

## 2. Model Responsibilities (FROZEN)

| Model              | Positioning                          | Notes                                            |
| ------------------ | ------------------------------------ | ------------------------------------------------ |
| `LogDistanceChannel` | deterministic baseline             | Closed-form PL(d) = PL0 + 10·n·log10(d/r0).      |
| `ShadowingChannel`   | large-scale + Gaussian shadowing    | `ShadowingChannel(LogDistanceChannel)`, σ shadowing. |
| `RayleighChannel`    | small-scale fading                 | Composes a `LogDistanceChannel`; adds fast fading. |

**RayleighChannel — explicit constraints**:

- Does **NOT** inherit `LogDistanceChannel`. It is a sibling `ChannelModel` subclass.
- Reuses the path-loss math via **composition** (HAS-A `LogDistanceChannel` base), not inheritance.
- Maintains **type parallelism** — all three are peers under `ChannelModel`.
- Owns a private `Random(seed)`; samples fast fading `h ~ CN(0,1)` so `|h|² ~ Exp(1)`; overlays small-scale fading on top of the deterministic large-scale path loss.

---

## 3. Legacy Migration Conclusion (FROZEN)

**Legacy model** (removed in 5.2.2):

```text
Friis PL0
  +
n = 3.0
  +
σ = 4 shadowing   (random.gauss(0, 4.0))
```

**New architecture equivalent**:

```text
ChannelModelLinkAdapter(
    ShadowingChannel(sigma=4),
    environment="suburban"   # -> ENV_PATH_LOSS_EXPONENT["suburban"] = 3.0
)
```

- `sigma=4` reproduces the legacy `random.gauss(0, 4.0)` shadowing spread.
- `environment="suburban"` yields `n=3.0`, matching the legacy path-loss exponent.
- The reference loss `PL0 ≈ 31.21 dB` is consistent with the new model and the sensitivity table.

**Conclusion**:

> Statistical equivalence, **not** bit-level compatibility.

The two stacks produce the same statistical distribution of path loss / RSSI / PDR, but are not numerically identical sample-for-sample (different RNG path and small-scale model). This is the intended, accepted outcome of the migration.

---

## 4. Freeze Boundaries

**Frozen core — MUST NOT be modified by any channel work**:

```text
simulation.py
gateway_selector.py
packet.py
config.py
```

**Architecture rule**: any new channel model may enter **only**:

```text
simulator/channel_model/
```

**Forbidden (do not reintroduce)**:

```text
simulator/channel.py        # retired in 5.2.2
simulator/propagation.py    # retired in 5.2.2
```

The dual computation paths (legacy `PropagationModel` + new `ChannelModel`) are **forbidden from being restored**. The codebase shall maintain a single channel path through `ChannelModelLinkAdapter`.

---

## 5. Evolution Chain

```text
c6a02a6  refactor(channel): migrate legacy channel tests to ChannelModel
    |
    v
66730ff  test(channel): migrate gateway test to ChannelModel, drop legacy propagation test (5.2.1)
    |
    v
5efbbe7  refactor(channel): remove legacy propagation stack (5.2.2)
    |
    v
<this>   docs(channel): freeze ChannelModel architecture v1 (5.3)
```

Each node is an independent commit. **No squash.** History is preserved so the migration can be audited step by step.
