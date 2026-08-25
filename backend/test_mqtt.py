"""Sprint 5.1 MQTT / WebSocket 遥测测试（hermetic，不依赖真实 broker）。

运行：python -m backend.test_mqtt
验证：
  1) engine telemetry sink 收到 step 产生的每条记录（不依赖 broker）
  2) mqtt publish 的 topic 与 payload 正确（FakePaho 注入）
  3) broker 不可用时 publish 静默返回 False，绝不抛错
  4) /ws 能收到 engine.step 实时推送的 telemetry
"""

import json

from backend import mqtt_client
from backend.engine import SimulationEngine
from backend.main import app
from fastapi.testclient import TestClient


# ---------- 1. sink 收到 step 数据 ----------
def test_sink_receives_every_step():
    eng = SimulationEngine(seed=42)
    received = []
    eng.set_telemetry_sink(lambda rec: received.append(rec))
    eng.start()
    n = eng.step(20)
    assert n == 20, f"step 应执行 20，实际 {n}"
    assert len(received) == 20, f"sink 应收到 20 条，实际 {len(received)}"
    keys = {"time", "event", "node", "sf", "rssi", "snr", "gateway", "success"}
    for r in received:
        assert set(r.keys()) == keys
        assert r["event"] == "TRANSMIT"


# ---------- 2. mqtt publish topic + payload ----------
class FakePaho:
    def __init__(self):
        self.calls = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.calls.append((topic, payload, qos, retain))
        return None


def test_mqtt_publish_topic_and_payload():
    c = mqtt_client.MqttClient()
    fake = FakePaho()
    c._client = fake
    c.connected = True  # 模拟已连上 broker
    rec = {
        "time": 5.45, "event": "TRANSMIT", "node": "Node001", "sf": 7,
        "rssi": -104.6, "snr": 15.3, "gateway": "GW001", "success": True,
    }
    ok = c.publish("lora/device/data", rec, qos=0, retain=False)
    assert ok is True
    assert len(fake.calls) == 1
    topic, payload, qos, retain = fake.calls[0]
    assert topic == "lora/device/data"
    assert qos == 0 and retain is False
    sent = json.loads(payload)
    assert sent["node"] == "Node001"
    assert sent["success"] is True
    assert sent["event"] == "TRANSMIT"


# ---------- 3. 断连时静默降级 ----------
def test_mqtt_publish_noop_when_disconnected():
    c = mqtt_client.MqttClient()
    c._client = None
    c.connected = False
    # 不应抛异常，仅返回 False
    assert c.publish("lora/device/data", {"x": 1}) is False


# ---------- 4. /ws 实时推送 ----------
def test_ws_streams_telemetry():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            client.post("/api/simulation/reset")
            client.post("/api/simulation/start")
            client.post("/api/simulation/step?steps=3")
            msg = ws.receive_json()
            assert msg["event"] == "TRANSMIT"
            assert "node" in msg and "success" in msg
            assert msg["gateway"] in ("GW001", "GW002")


if __name__ == "__main__":
    test_sink_receives_every_step()
    test_mqtt_publish_topic_and_payload()
    test_mqtt_publish_noop_when_disconnected()
    test_ws_streams_telemetry()
    print("MQTT / WebSocket Test PASS")
