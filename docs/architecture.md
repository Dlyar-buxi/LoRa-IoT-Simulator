# Architecture

This document describes the layered architecture of **LoRa IoT Simulator**, with
emphasis on the **frozen simulation core** and the **Adapter boundary** that keeps
the backend from polluting it.

> **Golden rule:** `simulator/` and `gateway/` are frozen since Sprint 4. The
> backend never edits them, and the simulation core never imports any backend or
> frontend code.

---

## 1. Layered Architecture

```mermaid
flowchart LR
    FE[Web Dashboard\nfrontend/ — vanilla JS + SVG\nhttp://127.0.0.1:8000/] -->|REST /api/*| BE
    FE -->|WebSocket /ws| BE

    subgraph FastAPI Backend — backend/
        BE_APP[main.py · lifespan · ws_endpoint]
        ROUTES[routes.py · models.py]
        AUTH[auth.py · ApiKeyMiddleware + enforce_ws_token]

        subgraph ADAPTER[Adapter Layer — backend/engine.py]
            ENG[SimulationEngine singleton]
            HOOKS[Lifecycle hooks:\nregister_pre_reset_hook\nregister_reset_hook\nregister_pre_configure_hook\nregister_configure_hook]
            HIST[history: deque(maxlen=10000)]
            LOCK[_lock: threading.RLock]
            ENG <--> HOOKS
            ENG <--> HIST
            ENG <--> LOCK
        end

        BE_APP --> ROUTES --> ENG
        AUTH -- wraps --> BE_APP
    end

    ENG -->|step() / get_*()| CORE

    subgraph SIMULATOR CORE — FROZEN
        CORE[simulator/ + gateway/\nnodes · sensor · channel · mac · collision · scheduler\npropagation · energy · adr · gateway_selector · simulation]
    end

    ENG -. telemetry_sink(record) .-> SINK1
    ENG -. telemetry_sink(record) .-> SINK2
    ENG -. telemetry_sink(record) .-> SINK3
    SINK1[MQTT publish\nlora/device/data\nsilent degrade]
    SINK2[WebSocket broadcast\n/ws clients\nlive dashboard]
    SINK3[SQLite recorder\nexperiments.db\nsilent degrade]
```

### Responsibilities

| Layer | Directory | Role | Frozen? |
|-------|-----------|------|---------|
| Presentation | `frontend/` | Dashboard UI, real-time rendering | No |
| Authentication | `backend/auth.py` | `X-API-Key` header + `?token=` WS enforcement | No |
| Adapter | `backend/` | FastAPI app, REST/WS, telemetry sink, recorders, lifecycle hooks | No |
| Simulation Core | `simulator/` | LoRa PHY/MAC, energy, ADR, DES engine | **YES** |
| Network | `gateway/` | LoRa gateway / network layer | **YES** |

---

## 2. Data Flow

A single code path produces every downstream effect. The simulation core knows
nothing about any consumer.

```
simulator/simulation.py
   │
   └─> SimulationEngine.step()            # protected by threading.RLock
          │  (advances one discrete event from the heapq event queue)
          │
          ├─> history.append(record)      # deque(maxlen=10000) ring buffer
          │
          └─> if sink: sink(record)       # injected callable (Adapter)
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

## 3. Thread Safety & Concurrency Model

The Adapter lives inside a FastAPI process served by Uvicorn with a thread pool
for sync endpoints and a shared asyncio event loop for WebSocket — multiple
callers can race on `SimulationEngine` and on the WS client set at any time.
Every stateful surface is therefore guarded by a dedicated lock.

### 3.1 SimulationEngine lock (`threading.RLock`)

`backend/engine.py:SimulationEngine` owns a single `threading.RLock` called
`_lock`. A re-entrant lock is required because `get_history()` and
`get_export()` call other `get_*` helpers which each acquire the lock once,
and because sink callbacks occasionally re-enter read-only queries.

**All** of the following operations hold `_lock` for their entire duration:

| Operation | Mutates state? | Protected by |
|-----------|---------------|--------------|
| `step(n)` | Yes — pops heapq, appends history | `_lock` |
| `reset()` | Yes — rebuilds `Simulation`, clears history | `_lock` — also runs pre/post hooks inside the lock |
| `configure(**kw)` | Yes — rebuilds topology + ADR binding | `_lock` — also runs pre/post hooks inside the lock |
| `get_status() / get_nodes() / get_gateways() / get_statistics()` | No — read only | `_lock` |
| `get_history(bucket) / get_packets() / get_export()` | No — read only | `_lock` |
| `set_telemetry_sink(fn)` | Yes — swaps the callable | `_lock` |

Hook contracts:

- `register_pre_reset_hook(fn)` / `register_reset_hook(fn)`
- `register_pre_configure_hook(fn)` / `register_configure_hook(fn)`
- Any exception raised inside a hook is swallowed by `contextlib.suppress(Exception)`
  so a misbehaving recorder cannot stall a reset. Hooks are owned 100% by the
  Adapter — `engine.py` exposes a public register API and the caller in
  `main.py` wires DB begin/finalize into the right slot.

### 3.2 WsManager lock (`asyncio.Lock`)

`backend/main.py:WsManager` owns an `asyncio.Lock` instead of a threading
because every caller is a coroutine on the shared event loop (WebSocket
`accept`, `disconnect`, and `broadcast_sync` is bridged to async via
`asyncio.run_coroutine_threadsafe`). The lock guards:

- Adding a client to `_clients: set[WebSocket]` on connect.
- Removing a client on disconnect.
- Iterating `_clients` during broadcast to avoid a `Set changed size during
  iteration` crash from concurrent connect/disconnect.

### 3.3 SQLite recorder lock (`threading.Lock`)

`backend/database.py:Recorder._lock` is a non-re-entrant `threading.Lock`
that serialises:

- Batched `record_event()` appends + periodic `flush()` (WAL + executemany).
- `begin_experiment()` / `finalize_experiment()` / `close()`.

Because the SQLite module itself serialises one connection, our lock turns
"many small writes from the engine sink" into one batch write every 100 rows or
1 second — the actual path to storage is therefore single-writer, queue-free.

---

## 4. Authentication & API Key Enforcement

When the `API_KEY` environment variable is set at startup, every call into
the Adapter and realtime surface must present a valid key. When unset (local
development), the service behaves as before — a public learning platform.

### 4.1 REST endpoints — `X-API-Key` header

`backend/auth.py:ApiKeyMiddleware` is a `Starlette BaseHTTPMiddleware` that
runs before Starlette routing. It short-circuits for static files and
`GET /health`, then compares `request.headers.get("x-api-key")` against the
configured `_API_KEY`. On mismatch it returns a raw `JSONResponse(status_code=401)`
with a `{"detail": "Unauthorized"}` body.

Protected routes (all under `/api/*`, plus `/api` itself) carry the
enforcement automatically; the middleware owns the boundary.

### 4.2 WebSocket endpoint — `?token=` query

WebSocket upgrade does not have a reliable cross-browser custom-header path,
so the WS equivalent uses a query parameter. The enforcement is pure function
`enforce_ws_token(scope)` which:

1. Extracts `token=` from the ASGI querystring of the incoming `/ws` upgrade.
2. Compares against `_API_KEY` (returns `None` on match, or a dict
   `{"type": "http.response.start", ...}` + body tuple on failure).
3. Is invoked **inline** at the top of `ws_endpoint` in `main.py`, before
   `await websocket.accept()`. If it returns failure frames, the handler
   pushes them onto `websocket._raw_receive` and returns without accepting.

### 4.3 Surface coverage

| Surface | Enforcement |
|---------|-------------|
| `POST /api/simulation/*` (start / pause / step / stop / reset / config) | `X-API-Key` header |
| `GET  /api/nodes` · `/gateways` · `/statistics` · `/history` · `/packets` · `/export/json` | `X-API-Key` header |
| `GET  /api/experiments` · `/api/experiments/{id}` | `X-API-Key` header |
| `ws://…/ws?token=<key>` realtime telemetry | `?token=` query |
| Static frontend `/index.html` · dashboard assets · `GET /health` | Always public — needed to bootstrap the UI |

---

## 5. Adapter Boundary

The Adapter layer (`backend/engine.py` + `backend/main.py`) is the **only** place
that touches both the frozen core and nothing else crosses the line.

```
backend/engine.py:
    class SimulationEngine:
        def __init__(self, ...):
            self._sim = Simulation(...)        # frozen core, used read-only
            self._lock = threading.RLock()
            self._hooks: {pre_reset, post_reset, pre_configure, post_configure}

        def step(self, n=1):
            with self._lock:
                record = self._sim.step()     # call into core
                if self._sink: self._sink(record) # notify Adapter sinks
                return record

        def reset(self):
            with self._lock:
                self._run_hooks(pre_reset)
                self._sim.rebuild(...)
                self._run_hooks(post_reset)

        def configure(self, **kw):
            with self._lock:
                self._run_hooks(pre_configure)
                self._build(**kw)
                self._run_hooks(post_configure)

        def get_* (self):
            with self._lock: return self._sim.get_*()

        def set_telemetry_sink(self, fn):
            with self._lock: self._sink = fn
```

**What the Adapter may do:**

- Instantiate and call the frozen `Simulation`.
- Inject a `telemetry_sink` callable.
- Register lifecycle hooks (`register_pre_reset_hook` / `register_reset_hook` /
  `register_pre_configure_hook` / `register_configure_hook`) to bracket experiment
  lifecycle (finalize old experiment → reset/configure → begin new experiment).
  Hook registration lives in `main.py`; `engine.py` only exposes the public
  register API.
- Bind `config.ADR_ENABLED` at runtime inside `_build()` (no edit to `config.py`).

**What the Adapter must NOT do:**

- Edit any file under `simulator/` or `gateway/`.
- Import backend state into the core.

---

## 6. Frozen Core Design

The simulation core is **frozen since Sprint 4** (across Sprints 4.4 → 5.3 → 6.2). Every
feature added afterward (visualization, MQTT, SQLite, parameterization, thread safety,
API Key auth) was layered *around* it, never *into* it.

| Sprint | What changed | Core touched? |
|--------|--------------|---------------|
| 4.4 | Visualization platform (Dashboard) | No — new `backend/` + `frontend/` |
| 5.1 | MQTT realtime telemetry | No — new `mqtt_client.py` + sink branch |
| 5.2 | SQLite experiment persistence | No — new `database.py` + sink branch |
| 5.3 | Parameterized experiment platform | No — `configure()` + hooks injected, ADR runtime-bound |
| v1.2 hardening | RLock engine, deque history, WAL+batch DB, chained setTimeout auto-run | No — all Adapter/frontend |
| v1.2 auth | API Key middleware + WS token check | No — all Adapter |

**Proof of discipline:** `git diff --stat -- simulator/ gateway/` is empty after
every sprint. The frozen-core diff is always empty.

**Why it matters for the resume:**
- Demonstrates clean separation of concerns and a stable contract.
- Lets the simulation be reused/tested in isolation (it runs on the standard
  library alone — `python simulator/main.py`).
- Makes the Adapter a safe, swappable integration surface.

---

## 7. telemetry_sink Design

The sink is a **single injected callable** — not a queue, thread pool, or observer
framework. This keeps the core simple and dependency-free.

```python
# backend/main.py
def telemetry_sink(record: dict):
    mqtt.publish("lora/device/data", record)  # (1) optional, silent
    if ws_manager.has_clients():
        ws_manager.broadcast_sync(json.dumps(record))  # (2) live dashboard
    recorder.record_event(record)  # (3) optional, silent
```

Properties:
- **Injected, not hardcoded.** `engine.set_telemetry_sink(telemetry_sink)` is
  called in the FastAPI `lifespan`; clearing it (`None`) is also supported.
- **Fail-soft.** Each branch catches its own failure (MQTT disconnected, WS empty,
  DB unavailable) and never raises into `step()`. Each sink branch is wrapped
  with `contextlib.suppress(Exception)` or an equivalent narrow try/except.
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

## 8. Environment Configuration

All external integrations are env-driven and default to "working, but optional".

| Variable | Default | Consumed by | Effect |
|----------|---------|-------------|--------|
| `MQTT_BROKER_URL` | `mqtt://localhost:1883` | `backend/mqtt_client.py` | Broker address for telemetry export |
| `DB_ENABLED` | `true` | `backend/database.py` | Master switch for SQLite recording |
| `DB_PATH` | `experiments.db` | `backend/database.py` | SQLite file location |
| `API_KEY` | (unset = no auth) | `backend/auth.py` + `main.py` ws_endpoint | Enforces `X-API-Key` on REST + `?token=` on WebSocket |
| `ENGINE_HISTORY_MAX_LEN` | `10000` | `backend/engine.py` | `deque(maxlen=…)` cap on engine telemetry ring buffer |
| `DB_BATCH_FLUSH_COUNT` / `DB_BATCH_FLUSH_SECONDS` | `100` / `1.0` | `backend/database.py` | WAL batch write thresholds |

If `DB_ENABLED=false` or the file is unwritable, recording degrades silently and
`GET /api/experiments` returns an empty list.

---

## 9. Default Experiment

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
