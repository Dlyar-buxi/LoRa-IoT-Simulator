# Architecture

This document describes the layered architecture of **LoRa IoT Simulator**, with
emphasis on the **frozen simulation core** and the **Adapter boundary** that keeps
the backend from polluting it.

> **Golden rule:** `simulator/` and `gateway/` are frozen since Sprint 4. The
> backend never edits them, and the simulation core never imports any backend or
> frontend code.

---

## 1. Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Dashboard (frontend/)                │
│        vanilla JS + SVG  ·  served at http://127.0.0.1:8000/ │
└───────────────▲───────────────────────────┬─────────────────┘
                │ REST (/api/*)             │ WebSocket (/ws)
┌───────────────┴───────────────────────────▼─────────────────┐
│                   FastAPI Backend (backend/)                 │
│   main.py (app, lifespan, ws) · routes.py · models.py        │
│                                                               │
│   ┌─────────────────────────────────────────────────────┐   │
│   │            ADAPTER LAYER (backend/engine.py)         │   │
│   │  - wraps SimulationEngine singleton                  │   │
│   │  - injects telemetry_sink                            │   │
│   │  - monkeypatches reset/configure (exp lifecycle)     │   │
│   │  - runtime ADR binding via config.ADR_ENABLED        │   │
│   └───────────────────────▲─────────────────────────────┘   │
│                           │ step() / get_*()                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              SIMULATOR CORE  (simulator/, gateway/)          │
│   nodes · sensor · channel · mac · collision · scheduler ·   │
│   propagation · energy · adr · gateway_selector · simulation │
│   ★ FROZEN — byte-level unchanged since Sprint 4            │
└─────────────────────────────────────────────────────────────┘
```

### Responsibilities

| Layer | Directory | Role | Frozen? |
|-------|-----------|------|---------|
| Presentation | `frontend/` | Dashboard UI, real-time rendering | No (out of scope for edits this sprint) |
| Adapter | `backend/` | FastAPI app, REST/WS, telemetry sink, recorders | No (this is where packaging lives) |
| Simulation Core | `simulator/` | LoRa PHY/MAC, energy, ADR, DES engine | **YES** |
| Network | `gateway/` | LoRa gateway / network layer | **YES** |

---

## 2. Data Flow

A single code path produces every downstream effect. The simulation core knows
nothing about any consumer.

```
simulator/simulation.py
   │
   └─> SimulationEngine.step()
          │  (advances one discrete event from the heapq event queue)
          │
          ├─> history.append(record)            # in-engine ring buffer
          │
          └─> if sink: sink(record)             # injected callable (Adapter)
                 │
                 ├─(1) MQTT     publish "lora/device/data"   [optional, silent degrade]
                 ├─(2) WebSocket broadcast to /ws clients   [live dashboard]
                 └─(3) SQLite   recorder.record_event(record)[optional, silent degrade]

   Separately, the Adapter serves queries via REST/WS:
       engine.get_status() / get_nodes() / get_gateways()
       / get_statistics() / get_packets() / get_history() / get_export()
           └─> backend/routes.py  ──>  frontend rendering
```

**Key property:** the three telemetry exits (1)(2)(3) are *sinks*. They are
notified by the engine; the engine does not depend on them. If any sink fails,
the engine keeps running.

---

## 3. Adapter Boundary

The Adapter layer (`backend/engine.py` + `backend/main.py`) is the **only** place
that touches both the frozen core and nothing else crosses the line.

```
backend/engine.py:
    class SimulationEngine:
        def __init__(self, ...):
            self._sim = Simulation(...)        # frozen core, used read-only
        def step(self, n=1):
            record = self._sim.step()         # call into core
            if self._sink: self._sink(record) # notify Adapter sinks
            return record
        def get_* (self):  return self._sim.get_*()   # read-only queries
        def configure(self, **kw):            # Sprint 5.3 entry point
            self._sim.???                     # rebuild topology in-core
            config.ADR_ENABLED = self.adr_enabled  # runtime ADR binding
        def set_telemetry_sink(self, fn): self._sink = fn
```

**What the Adapter may do:**
- Instantiate and call the frozen `Simulation`.
- Inject a `telemetry_sink` callable.
- Monkeypatch `engine.reset` / `engine.configure` to bracket experiment lifecycle
  (finalize old experiment → reset/configure → begin new experiment) — this lives
  in `main.py`, the `engine.py` *file* stays untouched.
- Bind `config.ADR_ENABLED` at runtime inside `_build()` (no edit to `config.py`).

**What the Adapter must NOT do:**
- Edit any file under `simulator/` or `gateway/`.
- Import backend state into the core.

---

## 4. Frozen Core Design

The simulation core is **frozen since Sprint 4** (across Sprints 4.4 → 5.3). Every
feature added afterward (visualization, MQTT, SQLite, parameterization) was layered
*around* it, never *into* it.

| Sprint | What changed | Core touched? |
|--------|--------------|---------------|
| 4.4 | Visualization platform (Dashboard) | No — new `backend/` + `frontend/` |
| 5.1 | MQTT realtime telemetry | No — new `mqtt_client.py` + sink branch |
| 5.2 | SQLite experiment persistence | No — new `database.py` + sink branch |
| 5.3 | Parameterized experiment platform | No — `configure()` injected, ADR runtime-bound |

**Proof of discipline:** `git diff --stat -- simulator/ gateway/` is empty after
every sprint. The frozen-core diff is always empty.

**Why it matters for the resume:**
- Demonstrates clean separation of concerns and a stable contract.
- Lets the simulation be reused/tested in isolation (it runs on the standard
  library alone — `python simulator/main.py`).
- Makes the Adapter a safe, swappable integration surface.

---

## 5. telemetry_sink Design

The sink is a **single injected callable** — not a queue, thread pool, or observer
framework. This keeps the core simple and dependency-free.

```python
# backend/main.py
def telemetry_sink(record: dict):
    mqtt.publish("lora/device/data", record)        # (1) optional, silent
    if ws_manager.has_clients():
        ws_manager.broadcast_sync(json.dumps(record))# (2) live dashboard
    recorder.record_event(record)                   # (3) optional, silent
```

Properties:
- **Injected, not hardcoded.** `engine.set_telemetry_sink(telemetry_sink)` is
  called in the FastAPI `lifespan`; clearing it (`None`) is also supported.
- **Fail-soft.** Each branch catches its own failure (MQTT disconnected, WS empty,
  DB unavailable) and never raises into `step()`.
- **No framework.** `WsManager` is one Python `set` + an asyncio bridge; the
  SQLite recorder uses the stdlib `sqlite3` module; MQTT uses `paho-mqtt`. No
  queues, no background worker threads owned by this project.

### Three exits, one source

| Exit | Mechanism | Required? | Degrade behavior |
|------|-----------|-----------|------------------|
| MQTT | `paho-mqtt` publish | No | Broker down → publish returns `False`, sim continues |
| WebSocket | `FastAPI` ws broadcast | No | No clients → skip |
| SQLite | `sqlite3` insert | No | DB error → logged, returns `False`, sim continues |

---

## 6. Environment Configuration

All external integrations are env-driven and default to "working, but optional".

| Variable | Default | Consumed by | Effect |
|----------|---------|-------------|--------|
| `MQTT_BROKER_URL` | `mqtt://localhost:1883` | `backend/mqtt_client.py` | Broker address for telemetry export |
| `DB_ENABLED` | `true` | `backend/database.py` | Master switch for SQLite recording |
| `DB_PATH` | `experiments.db` | `backend/database.py` | SQLite file location |

If `DB_ENABLED=false` or the file is unwritable, recording degrades silently and
`GET /api/experiments` returns an empty list.

---

## 7. Default Experiment

These come from the frozen `simulator/config.py` and are reflected in the database
metadata once the backend starts:

| Parameter | Default |
|-----------|---------|
| Area size | 2000 m × 2000 m |
| Node count | 200 |
| Gateway count | 2 |
| Frequency / Bandwidth | 868 MHz / 125 kHz |
| Default SF | 7 |
| ADR enabled | True |
| Seed | 42 |
| Path-loss exponent | 2.8 |

The parameterization platform (Sprint 5.3) lets you override node count, area,
gateway placement, seed, duration, and ADR at runtime via `POST /api/simulation/config`
— without editing `config.py`.
