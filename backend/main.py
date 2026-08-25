"""FastAPI 入口（Sprint 4.4.1 ~ 5.1）。

提供 REST API（/api/*），并托管前端 Dashboard（frontend/ 静态文件）。
Backend 作为 Adapter：包裹冻结的 simulator.Simulation 引擎，并兼任自身 UI 的
Web 服务器（根路径 / 直接提供 frontend/index.html，同源免 CORS）。
路由只读查询，不修改任何冻结模块。

Sprint 5.1 新增：
- 进程内 WebSocket 管理器（/ws），把仿真遥测实时推给 Dashboard。
- telemetry sink：engine.step() 每产生一条记录，同时发布到 MQTT Broker
  （外部遥测出口，可选）并广播给所有 WS 客户端。
- MQTT 经 mqtt_client（懒连接，broker 不可用静默降级）。
- SQLite 实验记录器（Sprint 5.2）：telemetry sink 第三出口，将每条遥测记录
  落盘为可回放 / 可对比的实验（experiments + events），DB 不可用静默降级。
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from simulator import config
from .engine import engine, GATEWAY_POSITIONS
from .mqtt_client import mqtt
from .database import recorder
from .routes import router

logging.basicConfig(level=logging.INFO)

# frontend/ 位于项目根（backend 的上一级），与 backend 同属本服务，同源免 CORS
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)

# ---------- 进程内 WebSocket 管理器 ----------
class WsManager:
    """维护 WS 客户端集合，并向其广播遥测文本。

    仅一个 Python set + 捕获主事件循环；不引入 queue / thread 框架。
    """

    def __init__(self):
        self._clients = set()
        self._loop = None

    def attach_loop(self, loop):
        self._loop = loop

    def has_clients(self):
        return bool(self._clients)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self._clients.discard(ws)

    async def broadcast(self, message: str):
        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                self._clients.discard(ws)

    def broadcast_sync(self, message: str):
        """从同步上下文（engine.step 内）桥接广播到事件循环。"""
        if not self._clients or self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)


ws_manager = WsManager()


# ---------- telemetry sink（Engine -> MQTT + WS + SQLite）----------
def telemetry_sink(record: dict):
    # 1) MQTT 外部出口（broker 不可用时 publish 静默返回 False）
    mqtt.publish("lora/device/data", record, qos=0, retain=False)
    # 2) WebSocket 实时广播给 Dashboard（经主事件循环桥接）
    if ws_manager.has_clients():
        ws_manager.broadcast_sync(json.dumps(record, ensure_ascii=False))
    # 3) SQLite 实验记录器（DB 不可用 / 写入异常时 record_event 静默返回 False）
    recorder.record_event(record)


# ---------- 实验记录生命周期（Adapter 层，不修改 engine.py）----------
def _experiment_meta():
    """从 engine / config 采集实验元信息（不反向依赖仿真代码）。"""
    return {
        "seed": engine.seed,
        "node_count": config.NODE_COUNT,
        "duration": engine.duration,
        "area_size": config.AREA_SIZE,
        "adr_enabled": config.ADR_ENABLED,
        "gateway_cfg": GATEWAY_POSITIONS,
    }


def _collect_final_state():
    """终态采集回调：拉 engine 当前快照供 finalize 落盘。"""
    try:
        return {
            "final_stats": engine.get_statistics(),
            "nodes": engine.get_nodes(),
            "gateways": engine.get_gateways(),
        }
    except Exception:
        return {}


def _finalize_current_experiment():
    recorder.finalize_experiment(**_collect_final_state())


def _begin_new_experiment():
    recorder.begin_experiment(_experiment_meta())


# reset -> 关闭旧实验并开新实验（不覆盖旧实验）；engine.py 文件保持零修改
_orig_reset = engine.reset
def _reset():
    _finalize_current_experiment()
    _orig_reset()
    _begin_new_experiment()
engine.reset = _reset


# ---------- 生命周期：捕获主循环 + 懒连 MQTT ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.attach_loop(asyncio.get_running_loop())
    mqtt.connect()  # 失败静默降级，不影响应用启动
    recorder.connect()  # 失败静默降级（DB_ENABLED=false 或文件不可写）
    recorder.set_finalizer(_collect_final_state)
    _begin_new_experiment()  # 首实验上下文（engine 已 ready）
    engine.set_telemetry_sink(telemetry_sink)
    yield
    engine.set_telemetry_sink(None)
    _finalize_current_experiment()  # 进程退出前收尾
    recorder.close()
    mqtt.disconnect()


app = FastAPI(
    title="LoRa-IoT-Simulator Backend",
    description="LoRa 智慧农业 / 工业物联网 网络仿真与监控平台 — REST API + WebSocket + Dashboard",
    version="5.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """实时遥测通道：连接后接收每条 device/data 记录（JSON 文本）。"""
    ws_manager.attach_loop(asyncio.get_running_loop())
    await ws_manager.connect(websocket)
    try:
        # 保持连接；客户端可发任意文本作心跳，这里仅接收并忽略
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# 托管前端 Dashboard：根路径 / 直接返回 frontend/index.html（同源，免 CORS）
# 必须在 /ws 之后挂载，否则 "/" 挂载会优先拦截 /ws 的 websocket scope。
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
