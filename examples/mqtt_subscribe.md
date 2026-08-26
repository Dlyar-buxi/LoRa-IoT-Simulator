# MQTT Subscribe Example

The simulator publishes every telemetry record to the MQTT topic
**`lora/device/data`** (QoS 0). The broker is **optional** — if it is
unreachable the publish silently fails and the simulation continues.

## 1. Start a broker (optional)

Any MQTT 3.1.1/5.0 broker works. With Mosquitto:

```bash
# Debian/Ubuntu
sudo apt-get install -y mosquitto mosquitto-clients

# macOS
brew install mosquitto
brew services start mosquitto
```

The simulator connects to `MQTT_BROKER_URL` (default `mqtt://localhost:1883`).
Override it via environment variable before launching the backend:

```bash
export MQTT_BROKER_URL=mqtt://localhost:1883
uvicorn backend.main:app --reload
```

## 2. Subscribe with the CLI

```bash
mosquitto_sub -h localhost -p 1883 -t "lora/device/data" -v
```

You will see one JSON line per simulation event as the engine steps:

```json
{"time": 12.3, "event": "tx", "node": "n7", "sf": 7,
 "rssi": -101.2, "snr": 5.5, "gateway": "gw2", "success": true}
```

## 3. Subscribe with Python (paho-mqtt)

```python
import json
from paho.mqtt import client as mqtt


def on_connect(c, u, f, rc, *a):
    print("connected, rc =", rc)
    c.subscribe("lora/device/data")


def on_message(c, u, msg):
    rec = json.loads(msg.payload)
    print(
        f"node={rec['node']} sf={rec['sf']} "
        f"rssi={rec['rssi']} gw={rec['gateway']} ok={rec['success']}"
    )


c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="lora-subscriber")
c.on_connect = on_connect
c.on_message = on_message
c.connect("localhost", 1883, keepalive=60)
c.loop_forever()
```

## Field reference (per record)

| Field | Meaning |
|-------|---------|
| `time` | Simulation time (seconds) of the event |
| `event` | Event type, e.g. `tx` (transmission) |
| `node` | Source node id |
| `sf` | Spreading factor in use |
| `rssi` | Received signal strength (dBm) at the gateway |
| `snr` | Signal-to-noise ratio (dB) |
| `gateway` | Selected gateway id (best RSSI) |
| `success` | `true` if the packet was received, `false` otherwise |

> Because the same `record` is also pushed to the WebSocket dashboard and written
> to SQLite, MQTT is purely an *additional* export — you can disable it entirely
> (broker down, or remove the broker) without affecting simulation or persistence.
