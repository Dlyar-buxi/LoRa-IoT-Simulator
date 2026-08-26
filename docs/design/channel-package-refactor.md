# Channel Package Refactor — Design Freeze (Task 2.4)

> Status: **Frozen** — implementation must follow this contract exactly.
> Parent: ADR-001 (`docs/adr/ADR-001-channel-model-architecture.md`)
> Preceded by: `docs/design/channel-model-api.md`, `docs/design/shadowing-channel.md`
> Branch: `channel-model-api` → remote `feature/channel-model-api` (Strategy A)
> Milestone context: **Multi-model Channel Architecture v0.1** (LogDistance + Shadowing)

---

## 1. Goal

Promote the channel abstraction from a *single-file* layout to an *extensible
package* layout, so that the third and later models (Rayleigh / Urban / ML /
DigitalTwin) drop in as plain subclasses with **zero importer churn**.

```
single file abstraction   ──▶   extensible channel framework
```

This is a **pure structural refactor**. It adds **no new capability**, changes
**no behavior**, and preserves **every existing import path**.

### Non-goals

- No new channel model (that is Task 4 / RayleighChannel).
- No behavior change in `evaluate()`, PDR, SNR, shadowing, or adapter logic.
- No touching of frozen core: `simulation.py`, `gateway_selector.py`,
  `packet.py`, `config.py`, `propagation.py`, `channel.py` stay byte-stable
  (except `simulation.py` already depends only on the `channel_model` import,
  which the shim preserves — see §4).
- No removal of legacy `LoRaChannel` (that is Task 5).

---

## 2. Target Layout

```
simulator/
├── channel_model/               # ← NEW package (real home of the abstraction)
│   ├── __init__.py              # re-exports all public names
│   ├── base.py                  # TransmissionContext, ChannelResult, ChannelModel(ABC)
│   ├── log_distance.py          # LogDistanceChannel(ChannelModel)
│   ├── shadowing.py             # ShadowingChannel(LogDistanceChannel)
│   └── adapter.py               # ChannelModelLinkAdapter
├── channel.py                   # legacy module (LoRaChannel) — UNTOUCHED (Task 5 removes it)
├── shadowing_channel.py         # ← becomes a COMPAT SHIM (re-exports from channel_model/)
├── test_channel_model.py        # unchanged (imports simulator.channel_model)
├── test_channel_model_validation.py  # unchanged
└── test_shadowing_channel.py    # unchanged (imports simulator.shadowing_channel)
```

> **Naming note (deviation from first draft).** The package is named
> `simulator/channel_model/` — **not** `simulator/channel/` as originally
> drafted. Reason: `simulator/channel.py` (legacy `LoRaChannel`) already exists,
> and a same-named package `simulator/channel/` would collide with and shadow
> that module, breaking `from simulator.channel import LoRaChannel` (used by
> `test_gateway_selection.py`, `test_channel.py`, `simulation.py`,
> `gateway_selector.py`). Renaming the legacy module is Task 5 scope (touches
> frozen core), so the new package keeps the `channel_model` path — which also
> means every existing `from simulator.channel_model import ...` call site needs
> **zero changes**.

### Module ownership

| Symbol | New home |
|---|---|
| `TransmissionContext` | `channel_model/base.py` |
| `ChannelResult` | `channel_model/base.py` |
| `ChannelModel` (ABC) | `channel_model/base.py` |
| `LogDistanceChannel` | `channel_model/log_distance.py` |
| `ShadowingChannel` | `channel_model/shadowing.py` |
| `ChannelModelLinkAdapter` | `channel_model/adapter.py` |

`channel_model/__init__.py` re-exports all six so that
`from simulator.channel_model import ChannelModel, ...` keeps working (this was
already the import path; the package now backs it instead of a single file).

---

## 3. Migration Mechanics

> **As-built (post-collision fix).** The first draft planned a `simulator/channel/`
> package + `channel_model.py` shim. That collides with legacy `simulator/channel.py`
> (see §2 note), so the as-built approach is: **delete the `channel_model.py`
> module and back the `simulator.channel_model` import path with a package
> directory instead.**

1. **Delete `simulator/channel_model.py`** (the old single-file module).
2. **Create `simulator/channel_model/`** package (5 files: `__init__.py`,
   `base.py`, `log_distance.py`, `shadowing.py`, `adapter.py`). Move the *real*
   implementations verbatim from the deleted module / `shadowing_channel.py`
   into the package (no logic edits — only file boundaries change).
   Intra-package imports use `simulator.channel_model.base` etc.
3. **Convert `simulator/shadowing_channel.py` into a shim** (re-export
   `ShadowingChannel` from `simulator.channel_model`), so
   `test_shadowing_channel.py` needs **no edit**.
4. **Do NOT edit** any test file, `simulation.py`, `gateway_selector.py`, or
   `packet.py`. Their current imports (`from simulator.channel_model import …`,
   `from simulator.shadowing_channel import …`) keep resolving through the
   package `__init__` / shim. `simulator/channel.py` (legacy `LoRaChannel`) is
   left completely untouched.

### Why back the path with a package (not a shim)

Because `simulator.channel_model` was *already* the public import path used by
`simulation.py` and the tests, turning the module into a package of the same
name means **every existing call site needs zero changes** — the package
`__init__.py` simply re-exports the same symbols. No shim file is required for
`channel_model`; only `shadowing_channel.py` remains a thin shim (because it
points at the now-relocated `ShadowingChannel`).

---

## 4. Backward-Compat Contract (must hold after refactor)

These exact import lines MUST continue to work unchanged:

```python
# simulation.py (frozen core — must NOT be edited)
from simulator.channel_model import ChannelModelLinkAdapter, LogDistanceChannel

# test_channel_model.py
from simulator.channel_model import (
    ChannelModel, ChannelResult, LogDistanceChannel,
    TransmissionContext, ChannelModelLinkAdapter,
)

# test_channel_model_validation.py
from simulator.channel_model import (
    ChannelModel, ChannelResult, LogDistanceChannel,
    TransmissionContext, ChannelModelLinkAdapter, MockChannel,
)

# test_shadowing_channel.py
from simulator.shadowing_channel import ShadowingChannel
from simulator.channel_model import LogDistanceChannel, TransmissionContext
```

New code (Task 4+) imports from `simulator.channel_model` (the package now
backing that path). `simulator.shadowing_channel` remains a thin shim until
Task 5 removes `LoRaChannel` and we can cleanly collapse the shims.

---

## 5. Validation / Acceptance

All of the following MUST pass after the refactor; any failure blocks merge:

- [ ] `python -m simulator.test_channel_model` — contract + adapter PASS
- [ ] `python -m simulator.test_channel_model_validation` — 3 validation tests PASS
- [ ] `python -m simulator.test_shadowing_channel` — seed / distribution / backward-compat PASS
- [ ] `python -m simulator ... test_simulation` (`test_simulation_channel_integration`) PASS
- [ ] `python -m simulator.test_gateway_selection` — regression PASS
- [ ] `python -m simulator.test_channel` — legacy `LoRaChannel` regression PASS
- [ ] `python -m py_compile simulator/channel_model/*.py simulator/shadowing_channel.py` — OK
- [ ] Import smoke test:
      ```python
      from simulator.channel_model import ChannelModel, LogDistanceChannel, ShadowingChannel, ChannelModelLinkAdapter, TransmissionContext, ChannelResult, SPEED_OF_LIGHT, SF_SENSITIVITY, ENV_PATH_LOSS_EXPONENT
      from simulator.shadowing_channel import ShadowingChannel
      ```
- [ ] `git status --short` shows only: new `simulator/channel_model/` dir +
      `shadowing_channel.py` shim modification. No frozen-core file modified.

### Rollback condition

If any test in §5 fails, or any frozen-core file (`simulation.py`,
`gateway_selector.py`, `packet.py`, `config.py`, `channel.py`,
`propagation.py`) shows a diff, the refactor is **rejected** and the branch is
reset to the pre-refactor commit. The package add is additive and safe to drop.

---

## 6. Future (post-Task 2.4)

- **Task 4 — RayleighChannel**: add `simulator/channel_model/rayleigh.py`
  (`RayleighChannel(LogDistanceChannel)`), a new `test_rayleigh_channel.py`, and
  one benchmark row. No importer changes; optionally extend
  `channel_model/__init__.py` `__all__` if external code should see it via the
  `simulator.channel_model` path.
- **Task 5 — remove legacy**: migrate `gateway_selector.py` to
  `ChannelModelLinkAdapter`, delete `LoRaChannel` (`channel.py` →
  `legacy/channel.py` or remove), then retire the `shadowing_channel.py` shim.
  At that point `simulator.channel` is free and the package could even be
  renamed to `simulator/channel/`. Higher risk — done last.

---

## 7. Commit Message

```
refactor(channel): promote channel model to simulator/channel_model package

Move LogDistanceChannel/ShadowingChannel/ChannelModelLinkAdapter into the new
simulator/channel_model/ package (directory named channel_model/ because
simulator/channel.py (legacy LoRaChannel) already exists and would collide).
The simulator.channel_model import path is now backed by the package; only
shadowing_channel.py remains a backward-compat shim. No behavior change, no
frozen-core edits.
```
