# API Reference

Base URL: `http://127.0.0.1:8000`
Prefix: `/api`
OpenAPI docs: `http://127.0.0.1:8000/docs` (Swagger UI, served by FastAPI)

All payloads are JSON. The backend is a read/control **Adapter** over the frozen
simulation engine — it never mutates simulation source code.

---

## Simulation Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/simulation/start` | Begin running (pull model: sets the running flag; actual advancement happens via `/step`). |
| `POST` | `/api/simulation/pause` | Pause, preserving state; can be resumed with `start`. |
| `POST` | `/api/simulation/step?steps=N` | Advance `N` discrete events (default `1`, max `10000`). Returns status. |
| `POST` | `/api/simulation/stop` | Halt advancement, keep current state for inspection (no reset). |
| `POST` | `/api/simulation/reset` | Rebuild the simulation with the same seed → `t=0`, `received=0`, `pending=200`. |

All five return the engine **status** object:

```json
{
  "time": 1234.5,
  "state": "running",
  "generated": 540,
  "received": 498,
  "lost": 42,
  "pending": 200
}
```

---

## Configuration

### GET `/api/simulation/config`

Returns the currently active experiment parameters (the topology the next run will use).

```json
{
  "node_count": 200,
  "area_size": 2000,
  "gateway_positions": [["gw1", 1000, 1000], ["gw2", 0, 0]],
  "seed": 42,
  "duration": 3600,
  "adr_enabled": true
}
```

### POST `/api/simulation/config`

Inject topology parameters for the next run. **All fields are optional** — omitted
fields keep their current value. This is equivalent to a parameterized reset: it
rebuilds the in-core topology without creating a second engine, and does not affect
the existing `telemetry_sink`.

Request body (`ExperimentConfigIn`):

| Field | Type | Notes |
|-------|------|-------|
| `node_count` | int | `> 0` |
| `area_size` | float | square area side in meters |
| `gateways` | list of `[id, x, y]` | non-empty, unique ids, coords within `[0, area_size]` |
| `seed` | int | reproducibility seed |
| `duration` | float | simulation duration (seconds) |
| `adr_enabled` | bool | adaptive data rate toggle |

Example:

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

Validation failures return **HTTP 400** with a `detail` message:

| Condition | 400 detail |
|-----------|-----------|
| `node_count <= 0` | `"node_count must be > 0"` |
| `gateways` empty | `"gateways must be non-empty"` |
| duplicate gateway id | `"gateway ids must be unique"` |
| malformed gateway | `"gateway must be [id, x, y]"` |
| gateway coord out of area | `"gateway {id} coords ({x},{y}) out of area [0,{area}]"` |

On success returns the new active config (same shape as GET).

---

## Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/nodes` | All node snapshots: SF, RSSI/SNR, selected gateway, coords, battery, online status. |
| `GET` | `/api/gateways` | All gateway statistics: received packets, average RSSI, coordinates. |
| `GET` | `/api/statistics` | Network-level stats: throughput, PDR, retransmissions. |
| `GET` | `/api/history?bucket=1.0` | Time-bucketed link timeline (`bucket` > 0 seconds). |
| `GET` | `/api/packets?limit=N` | Event-level packet history (most recent `N`; omit for all). |
| `GET` | `/api/export/json` | Combined dump: status / nodes / gateways / statistics / packets / history. |

Example node snapshot:

```json
{
  "id": "n12",
  "sf": 7,
  "rssi": -98.3,
  "snr": 7.1,
  "gateway": "gw1",
  "x": 412.0, "y": 877.0,
  "battery": 96.4,
  "online": true
}
```

---

## Experiment (SQLite Persistence)

### GET `/api/experiments`

Lists persisted experiments (newest first). Each row summarizes one run:

```json
[
  {
    "id": 3,
    "seed": 42,
    "node_count": 200,
    "duration": 3600,
    "area_size": 2000,
    "adr_enabled": true,
    "created_at": "2026-08-26T00:02:18",
    "finalized": true
  }
]
```

If `DB_ENABLED=false` or the database is unavailable, returns an **empty list**
(silent degradation).

### GET `/api/experiments/{id}`

Returns the full experiment: metadata + final-state JSON (statistics / nodes /
gateways) + **all** per-event telemetry records (for replay / A/B comparison).

```json
{
  "id": 3,
  "seed": 42,
  "node_count": 200,
  "duration": 3600,
  "area_size": 2000,
  "gateway_cfg": [["gw1", 1000, 1000], ["gw2", 0, 0]],
  "adr_enabled": true,
  "created_at": "2026-08-26T00:02:18",
  "finalized": true,
  "statistics": { "pdr": 0.92, "throughput": 12.4, "retries": 38 },
  "nodes": [ /* final node snapshots */ ],
  "gateways": [ /* final gateway stats */ ],
  "events": [
    { "seq": 0, "time": 0.0, "event": "tx", "node": "n1",
      "sf": 7, "rssi": -95.0, "snr": 8.0, "gateway": "gw1", "success": true },
    { "seq": 1, "time": 0.5, "event": "tx", "node": "n2",
      "sf": 7, "rssi": -110.0, "snr": 2.0, "gateway": "gw1", "success": false }
  ]
}
```

If the experiment does not exist, returns **HTTP 404** with
`{"detail": "experiment not found"}`.

> A reset starts a **new** experiment and never overwrites a previous one, so you
> can compare runs with different parameters side by side.

---

## Realtime

### WebSocket `/ws`

Connect to `ws://127.0.0.1:8000/ws`. After the connection is accepted, every
simulation telemetry record is pushed as a JSON text message (the same record that
is also exported to MQTT and SQLite). The dashboard uses this channel for live
rendering; if no clients are connected, the engine simply skips the broadcast.

Example message (one per event):

```json
{"time": 12.3, "event": "tx", "node": "n7", "sf": 7,
 "rssi": -101.2, "snr": 5.5, "gateway": "gw2", "success": true}
```

### MQTT `lora/device/data`

Every telemetry record is also published to the MQTT topic `lora/device/data`
(QoS 0). The broker is **optional**:

- Configured via `MQTT_BROKER_URL` (default `mqtt://localhost:1883`).
- If the broker is unreachable, the publish silently fails and the simulation
  continues. See `examples/mqtt_subscribe.md` for a subscriber snippet.

---

## Testing the API

```bash
pip install -r requirements.txt
python -m pytest backend/ -q
```

Hermetic tests use `tempfile` / `:memory:` / `DB_ENABLED=false` and never touch the
project directory. Regression target: **12/12**.
