# LoRa IoT Simulator

A full-stack LoRa LPWAN network simulation & monitoring platform — from embedded
sensor nodes, through LoRa PHY/MAC and gateways, all the way to a live Web
dashboard with MQTT telemetry export and SQLite experiment persistence.

> The simulation core (`simulator/`, `gateway/`) is **frozen** since Sprint 4.
> The backend is a pure **Adapter** layer: the simulation core never imports any
> backend or frontend code, and has zero knowledge of MQTT, WebSocket, or SQLite.

## Features

- **Discrete-event LoRa simulation** — heap-based event scheduler (`heapq` DES).
- **LoRa PHY model** — log-distance path loss, shadow fading, RSSI/SNR, collision detection.
- **LoRa MAC** — pure ALOHA, retransmission with random backoff, **ADR** adaptive data rate.
- **Multi-gateway selection** — each node attaches to the gateway with the best RSSI.
- **FastAPI backend as Adapter** — wraps the frozen engine, exposes REST + WebSocket.
- **Real-time Dashboard** — vanilla JS + SVG: topology, PDR/RSSI curves, packet table (no external chart libs).
- **WebSocket telemetry** — every simulation event is pushed live to the browser.
- **MQTT telemetry export** — optional publish to `lora/device/data` (broker down = silent drop).
- **SQLite experiment persistence** — full topology + per-event telemetry recorded; replay & A/B compare.
- **Parameterized experiment platform** — inject node count / area / gateway placement / seed / ADR at runtime via REST.
- **Resilient by design** — MQTT, SQLite and WebSocket failures degrade silently; nothing crashes the sim.
- **Hermetic test suite** — 12/12 regression; frozen-core diff is always empty.

## Architecture

```
        FastAPI Backend (backend/)
                  |
        SimulationEngine  <-- Adapter layer (backend/engine.py)
                  |
        Simulator Core (Frozen: simulator/)
                  |
     +------------+------------+
     |            |            |
   MQTT       WebSocket      SQLite
 Telemetry    Dashboard      Recorder
(lora/       (/ws, live)   (experiments.db)
 device/
 data)
```

- **`simulator/`** — Core simulation layer (nodes, sensor, channel, MAC, energy, ADR). **Frozen.**
- **`gateway/`** — LoRa gateway / network layer. **Frozen.**
- **`backend/`** — Adapter layer: FastAPI app, REST + WS, telemetry sink, SQLite recorder, MQTT client.

### Data flow

```
simulator/simulation.py
   └─> SimulationEngine.step()
          └─> telemetry_sink(record)        # a single injected callable
                 ├─> MQTT  publish lora/device/data   (optional, silent degrade)
                 ├─> WS    broadcast to /ws clients    (live dashboard)
                 └─> SQLite recorder.record_event()    (optional, silent degrade)
          └─> get_*()  ->  REST /api/* + WS  ->  frontend rendering
```

### Frozen-core & Adapter boundary

- `simulator/` and `gateway/` are byte-level frozen since Sprint 4 (across Sprints 4.4 → 5.3).
- The backend never edits simulation code; it injects a `telemetry_sink` and a
  `configure()` entry point (runtime ADR binding via `config.ADR_ENABLED`).
- The simulation core has **zero knowledge** of MQTT, WebSocket, or SQLite — it only
  calls the injected sink during `step()`.

## Quick Start

Requirements: Python 3.12+

```bash
cd LoRa-IoT-Simulator
python -m venv venv
source venv/Scripts/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open the dashboard:

```
http://127.0.0.1:8000/
```

> **Note:** `python simulator/main.py` is the standalone Step-1 demo that prints
> 200 sample nodes to the console. It is **not** the web platform. Use `uvicorn`
> for the full dashboard + API experience.

Default experiment: **200 nodes, 2 gateways, 2000 m × 2000 m area, ADR enabled, seed 42**
(868 MHz, 125 kHz bandwidth, SF 7 default).

## Dashboard Demo

The dashboard (`frontend/`, served at `/`) provides:

- **Control bar** — Start / Pause / Step / Reset / Auto-run toggle.
- **KPI cards** — PDR, Throughput, Received, Lost, Simulation Time, Pending.
- **Grids** — node topology (SVG), PDR, SF distribution, RSSI map.
- **Packet table** — recent events streamed over WebSocket.

> Experiment parameters are configured through the REST API (see below). The
> dashboard itself does not yet expose a config panel — see Roadmap (5.5).

Press **Start** (or **Step**) and watch the topology and curves update in real time.

## Experiment Platform (Sprint 5.3)

Configure the next simulation run at runtime — no code changes, fully reproducible.

```bash
curl -X POST http://127.0.0.1:8000/api/simulation/config \
  -H "Content-Type: application/json" \
  -d '{
    "node_count": 100,
    "area_size": 2000,
    "seed": 42,
    "duration": 120,
    "adr_enabled": true
  }'
```

Read the active config:

```bash
curl http://127.0.0.1:8000/api/simulation/config
```

All fields are optional (omitted ones keep their current value). Validation returns
`400` for: `node_count <= 0`, an empty gateway list, duplicate gateway ids, or
gateway coordinates outside the area.

## MQTT Integration (Sprint 5.1)

Every telemetry record is published to `lora/device/data` (QoS 0). The broker is
**optional** — if it is unreachable the publish silently fails and the simulation
continues unaffected.

Configure via environment variable:

```
MQTT_BROKER_URL=mqtt://localhost:1883
```

See `examples/mqtt_subscribe.md` for a subscriber snippet.

## SQLite Persistence (Sprint 5.2)

Each simulation run is recorded as one experiment (`experiments` row) plus its
per-event telemetry (`events` rows). Experiments are kept across resets — a reset
starts a **new** experiment and never overwrites history.

```bash
curl http://127.0.0.1:8000/api/experiments          # list experiments
curl http://127.0.0.1:8000/api/experiments/1        # detail + events (replay/compare)
```

Configure via environment variables:

```
DB_ENABLED=true
DB_PATH=experiments.db
```

If the DB is unavailable, recording degrades silently and the API returns an empty list.

## API Reference

Base URL: `http://127.0.0.1:8000`  •  Prefix: `/api`  •  Full detail: [`docs/api.md`](docs/api.md)

### Simulation Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/simulation/start` | Begin running (pull model). |
| POST | `/api/simulation/pause` | Pause, keep state. |
| POST | `/api/simulation/step?steps=N` | Advance N discrete events (default 1). |
| POST | `/api/simulation/stop` | Halt advancing, keep state. |
| POST | `/api/simulation/reset` | Rebuild with same seed, back to t=0. |

### Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/simulation/config` | Current active config. |
| POST | `/api/simulation/config` | Inject topology params (400 on invalid). |

### Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/nodes` | Node snapshots (SF, RSSI/SNR, gateway, battery). |
| GET | `/api/gateways` | Gateway statistics. |
| GET | `/api/statistics` | Network PDR / throughput / retries. |
| GET | `/api/history?bucket=1` | Time-bucketed link timeline. |
| GET | `/api/packets?limit=N` | Event-level packet history. |
| GET | `/api/export/json` | Combined status/nodes/gateways/stats/packets/history. |

### Experiment
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/experiments` | List persisted experiments. |
| GET | `/api/experiments/{id}` | Detail + full events (404 if missing). |

### Realtime
- **WebSocket** — connect to `ws://127.0.0.1:8000/ws` to receive every telemetry record as JSON text.
- **MQTT** — subscribe to topic `lora/device/data`.

## Testing

```bash
pip install -r requirements.txt
python -m pytest backend/ -q
```

Hermetic tests use `tempfile` / `:memory:` / `DB_ENABLED=false` — they never
pollute the project directory. Regression target: **12/12**.

## Project Structure

```
LoRa-IoT-Simulator/
├── simulator/        # Frozen core: nodes, sensor, channel, MAC, energy, ADR
├── gateway/          # Frozen LoRa gateway / network layer
├── backend/          # FastAPI Adapter: engine, routes, mqtt_client, database, tests
├── frontend/         # Web dashboard (vanilla JS + SVG)
├── docs/             # architecture.md, api.md
├── examples/         # curl scripts & MQTT subscriber guide
├── screenshots/      # demo captures
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

> `network_server/` and `analysis/` are legacy early-stage modules **not wired into**
> the running platform; they are excluded from the live architecture above.

## Roadmap

| Sprint | Status | Content |
|--------|--------|---------|
| 1–3 | done | Skeleton, LoRa PHY/channel, MAC, collision, gateway |
| 4.4 | done | Visualization platform (Dashboard) |
| 5.1 | done | MQTT realtime telemetry |
| 5.2 | done | SQLite experiment persistence |
| 5.3 | done | Parameterized experiment platform |
| 5.4 | done | Project packaging (README, docs, examples, docker, screenshots) |
| 5.5 | idea | Dashboard Experiment Config Panel (frontend) |

## Resume Highlights

1. **End-to-end IoT full-stack** — embedded node → LoRa PHY/MAC → gateway → MQTT → FastAPI → Web.
2. **Self-built LoRa PHY+MAC simulation** — path loss, ALOHA collision, ADR, multi-gateway RSSI selection.
3. **Three-exit telemetry sink** — WebSocket + MQTT + SQLite from a single injected callable.
4. **Experiment persistence & replay** for A/B comparison of network configurations.
5. **Parameterized, reproducible experiments** via REST — no code changes to re-run a scenario.
6. **Clean Adapter architecture** with a frozen simulation core (zero reverse dependency).
7. **Resilient design** — every external sink degrades silently; no single point of failure.
8. **Test discipline** — hermetic pytest, 12/12 regression, frozen-core diff always empty.
9. **Minimal runtime dependencies** — only `fastapi`, `uvicorn`, `paho-mqtt`.
