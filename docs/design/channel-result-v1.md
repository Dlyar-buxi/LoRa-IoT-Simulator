# ChannelResult v1 — Design Freeze

- **Status**: FROZEN (design only, Sprint 6.4.0)
- **Baseline**: `dc3021e` (`docs(channel): freeze ChannelModel architecture v1`)
- **Scope**: `ChannelResult` contract + Adapter/Packet boundary
- **Out of scope (this doc)**: any `.py` change — 6.4.0 is design freeze only; implementation lands in 6.4.1 after approval.

---

## 1. Current State Audit (read-only, grounded in real code)

### 1.1 `ChannelResult` (simulator/channel_model/base.py:82)

Already a `@dataclass`, **5 fields, all stable**:

| Field               | Type  | Meaning                              |
| ------------------- | ----- | ------------------------------------ |
| `rssi`              | float | dBm, received signal strength        |
| `snr`               | float | dB, signal-to-noise ratio            |
| `pdr`               | float | 0..1, packet delivery probability    |
| `packet_received`   | bool  | **physical-layer success sample**    |
| `propagation_delay` | float | s, one-way propagation delay         |

> There is **no** `distance`, **no** `path_loss`, and **no** `success` field today.

### 1.2 Model output is already unified

All three models return the **identical** 5-field `ChannelResult`:

- `LogDistanceChannel.evaluate` → `ChannelResult(...)` (log_distance.py:102)
- `ShadowingChannel.evaluate` → `ChannelResult(...)` (shadowing.py:81)
- `RayleighChannel.evaluate` → `ChannelResult(...)` (rayleigh.py:104)

So the "unification gap" is **not** at the model layer — it is at the **result lifecycle / object boundary**.

### 1.3 Adapter flow (simulator/channel_model/adapter.py:39)

```text
packet + gateway
      |
      v  (distance computed from coords)
TransmissionContext
      |
      v
result = model.evaluate(context)   # LOCAL variable, NOT retained
      |
      v  (backfill 8 packet fields)
packet (mutated) -> returned
```

The `ChannelResult` is created but **discarded** (transient local). No first-class object survives the call.

### 1.4 Packet mirrors the channel result (simulator/packet.py)

`Packet` already carries the channel fields (packet.py:31-45):

```text
distance, gateway_id, rssi, snr, collision, success, retry_count,
pdr, packet_received, propagation_delay
```

→ `Packet` is **de-facto a ChannelResult**, blurring the model-output / sim-entity boundary.

### 1.5 Consumers read `packet.*` directly

| Consumer                       | Reads from Packet                        |
| ------------------------------ | ---------------------------------------- |
| `gateway/gateway.py` (receive) | `success`, `rssi`, `snr`                 |
| `simulator/simulation.py`      | `rssi`, `snr`, `success` (+ AND w/ collision) |
| `simulator/gateway_selector.py`| `rssi` (after `calculate_link`)          |

`pdr`, `packet_received`, `propagation_delay` are **written** by the adapter but only lightly consumed by the engine (mostly used in tests).

---

## 2. Problem Definition

1. **Result is transient.** `ChannelResult` is built and thrown away inside `calculate_link`; there is no retained handle for downstream / statistical use.
2. **Boundary blur.** Model output (`ChannelResult`) and sim entity (`Packet`) overlap; downstream couples to `Packet`'s channel fields instead of a clean result object.
3. **Naming hazard (correctness).** `success` ≠ `packet_received`.
   - `packet_received` = the channel's physical verdict (lives in `ChannelResult`).
   - `success` = `packet.success and not collided` (computed in `simulation.py:121`, lives on `Packet`).
   - Conflating them is a latent bug; the freeze must keep them distinct.
4. **Not self-describing.** `distance` / `path_loss` live only on `Packet` / inside the model; a standalone `ChannelResult` cannot answer "what was the path loss / distance for this link" — which blocks the Monte Carlo framework (6.4.2/6.4.3) from reading clean stats off the result.

---

## 3. Target Architecture

```text
Model
  |
  v
ChannelResult          (canonical, RETAINED, self-describing)
  |
  v
Adapter                (single Packet<-Result mapping; backward-compatible)
  |
  v
Packet                (sim entity; keeps fields for compatibility)
```

`ChannelResult` becomes the **retained, self-describing carrier** of one link's physical outcome. `Packet` keeps its fields as a stable compatibility surface.

---

## 4. ChannelResult Contract (FROZEN target)

| Field               | Type  | Source                         | Status        |
| ------------------- | ----- | ------------------------------ | ------------- |
| `rssi`              | float | `tx_power - path_loss (+fade)` | **stable**    |
| `snr`               | float | `rssi - noise_floor`           | **stable**    |
| `pdr`               | float | sigmoid(rssi - sensitivity)/3  | **stable**    |
| `packet_received`   | bool  | `rng.random() < pdr`           | **stable**    |
| `propagation_delay` | float | `distance / c`                 | **stable**    |
| `distance`          | float | engine geometry                | **6.4.1 add** |
| `path_loss`         | float | `PL0 + 10·n·log10(d/d0)`       | **6.4.1 add** |

- `distance` / `path_loss` are **proposed additions** for 6.4.1 (currently absent from `ChannelResult`); they make the result self-contained. Confirm in 6.4.1 approval.
- **`success` is intentionally NOT part of `ChannelResult`** — it is a higher-layer concept owned by `simulation.py`.

---

## 5. Migration Strategy (phased, non-breaking)

**Phase 1 — internal, zero consumer change (6.4.1):**
- Add `distance` / `path_loss` to `ChannelResult`.
- Adapter **retains** the result, e.g. `packet.channel_result = result` (a handle), keeping `calculate_link` return type = `packet`.
- No caller (simulation / gateway_selector / gateway) changes.

**Phase 2 — single owner (6.4.1 or 6.4.2):**
- Centralize the `Packet <- ChannelResult` field mapping into **one** adapter method. The 8 backfills currently in `calculate_link` get a single, testable owner.

**Phase 3 — optional, later sprint:**
- Consumers that need rich data read `packet.channel_result` instead of re-deriving from `packet.*`.
- `packet.rssi / snr / success` remain as a **stable compatibility surface** — no big-bang rewrite of `simulation.py`.

---

## 6. Compatibility Rules (forbidden)

- ❌ Delete any channel field on `Packet` (`rssi/snr/success/pdr/packet_received/propagation_delay/distance/gateway_id`).
- ❌ One-shot refactor of `simulation.py` / `gateway_selector.py` / `gateway/gateway.py`.
- ❌ Modify `ChannelModel.evaluate` physical algorithm — **fields may be added, math must not change**.
- ❌ Break the `calculate_link(packet, gateway)` signature (simulation / gateway_selector depend on it).
- ❌ Let `model.evaluate` have side effects or write back to any object.
- ❌ Treat `success` and `packet_received` as interchangeable.

---

## 7. Commit Boundary

```text
dc3021e  docs(channel): freeze ChannelModel architecture v1      (5.3)
    |
    v
<this>   docs(channel): freeze ChannelResult v1                 (6.4.0, doc only)
    |
    v
???????   refactor(channel): retain + enrich ChannelResult      (6.4.1, after approval)
```

- **6.4.0**: this document only — no code.
- **6.4.1**: `ChannelResult` field additions + adapter retain-handle + mapping centralization, as a **separate** commit after explicit approval.
- Design freeze and implementation stay in separate commits.

---

## 8. Decisions required before 6.4.1

1. Approve adding `distance` / `path_loss` to `ChannelResult`? (recommended: **yes**)
2. Approve `packet.channel_result = result` as the retained handle? (recommended: **yes**)
3. Consumers keep reading `packet.rssi/snr/success` forever (compat surface), or eventually migrate to `packet.channel_result`? (recommended: **keep compat, migrate only opt-in**)
