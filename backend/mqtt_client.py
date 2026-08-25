"""MQTT 客户端（Sprint 5.1）。

把仿真遥测作为**外部出口**发布到 MQTT Broker：
- broker URL 来自 env MQTT_BROKER_URL（默认 mqtt://localhost:1883）
- 懒连接：connect() 失败仅记日志，不阻断仿真
- publish() 全程 try/except：broker 不可用时静默丢弃，绝不抛错
- 单例 mqtt = MqttClient()

架构定位（见 Sprint 5.1 冻结设计）：
    Simulation Engine --> Telemetry Sink --> WebSocket (Dashboard)
                                      |--> MQTT Broker (optional)
MQTT 是外部遥测出口，不是系统运行依赖——broker 宕机不影响仿真与 Dashboard。
"""

from __future__ import annotations

import json
import logging
import os
import socket
from urllib.parse import urlparse

try:
    from paho.mqtt import client as paho_client

    try:
        from paho.mqtt.enums import CallbackAPIVersion
    except Exception:  # pragma: no cover - paho 1.x 没有 enums
        CallbackAPIVersion = None
    _PAHO = True
except Exception:  # pragma: no cover - 未安装 paho，MQTT 遥测自动禁用
    paho_client = None
    CallbackAPIVersion = None
    _PAHO = False

logger = logging.getLogger("lora.mqtt")

DEFAULT_BROKER_URL = "mqtt://localhost:1883"


def _parse_broker_url(url: str):
    """mqtt://host:port -> (host, port)。缺省回退到默认。"""
    if not url:
        url = DEFAULT_BROKER_URL
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 1883
    return host, port


class MqttClient:
    """极简 MQTT 发布客户端：broker 可选、失败静默降级。

    不引入 queue / thread / observer 框架——仅一个 paho Client + 全保护 publish。
    （paho 的 loop_start 是其内部网络线程，属库基础设施，非本项目自建线程。）
    """

    def __init__(self, broker_url: str | None = None):
        self.broker_url = broker_url or os.getenv("MQTT_BROKER_URL", DEFAULT_BROKER_URL)
        self.connected = False
        self._client = None
        if _PAHO:
            try:
                if CallbackAPIVersion is not None:
                    self._client = paho_client.Client(
                        CallbackAPIVersion.VERSION2, client_id="lora-sim-backend"
                    )
                else:  # paho 1.x
                    self._client = paho_client.Client(client_id="lora-sim-backend")
                self._client.on_connect = self._on_connect
                self._client.on_disconnect = self._on_disconnect
            except Exception as e:  # pragma: no cover
                logger.warning("MQTT Client 构造失败：%s — 遥测禁用", e)
                self._client = None

    # ---------- 连接（懒、非阻塞、失败降级）----------
    def connect(self, broker_url: str | None = None, keepalive: int = 60):
        """连接到 broker。失败仅记日志并返回 False，绝不抛错。"""
        if not _PAHO or self._client is None:
            logger.warning("paho-mqtt 不可用，MQTT 遥测已禁用")
            return False
        if broker_url:
            self.broker_url = broker_url
        host, port = _parse_broker_url(self.broker_url)
        try:
            # connect_async 非阻塞，避免 broker 不可达时阻塞应用启动；
            # loop_start 在后台线程跑网络循环，on_connect 回调置 connected。
            self._client.connect_async(host, port, keepalive=keepalive)
            self._client.loop_start()
            return True
        except (OSError, socket.error, ValueError) as e:
            logger.warning(
                "MQTT 连接失败（%s:%s）：%s — 遥测降级为静默丢弃", host, port, e
            )
            self.connected = False
            return False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code is None:
            self.connected = True
        else:
            try:
                self.connected = int(reason_code) == 0
            except Exception:
                self.connected = False
        if self.connected:
            logger.info("MQTT 已连接 %s", self.broker_url)
        else:
            logger.warning("MQTT 连接被拒绝：%s", reason_code)

    def _on_disconnect(self, client, userdata, *args):
        self.connected = False

    # ---------- 发布（全程保护，绝不抛错）----------
    def publish(self, topic: str, payload, qos: int = 0, retain: bool = False):
        """发布消息。未连接或异常时静默返回 False——不影响调用方。"""
        if not self.connected or self._client is None:
            return False
        try:
            if not isinstance(payload, (str, bytes)):
                payload = json.dumps(payload, ensure_ascii=False)
            self._client.publish(topic, payload, qos=qos, retain=retain)
            return True
        except Exception as e:  # 永不抛出
            logger.warning("MQTT 发布失败 topic=%s：%s", topic, e)
            return False

    def disconnect(self):
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self.connected = False


# 模块级单例（懒连接，应用启动时可选择 connect()）
mqtt = MqttClient()
