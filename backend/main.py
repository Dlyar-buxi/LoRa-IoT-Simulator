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
- 参数化实验平台（Sprint 5.3）：engine.configure(...) 注入 node_count / area_size /
  gateway_positions / seed / duration / adr_enabled；Simulation 核心与 config.py 冻结不动，
  ADR 经 _build 运行期绑定 config.ADR_ENABLED。
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from .engine import engine
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

    进程内单体：一个 asyncio.Lock 保护 _clients 读写 + 捕获主事件循环。

    P0-5：为什么要加锁 —— 所有 async 方法（connect/disconnect/broadcast）
    理论上都在同一个事件循环线程里跑，本来是串行的。但存在两个实际的
    并发面：
    1. `has_clients()` 被同步线程（sink）读，而 connect/disconnect 在 async
       线程写，属于跨线程的 TOCTOU。
    2. `broadcast_sync` 用 `run_coroutine_threadsafe` 把 broadcast 调度到
       事件循环，多个同步线程并发 sink 时，broadcast 内部的 list(...)
       迭代虽然不会 crash，但 has_clients 检查和实际 broadcast 之间
       客户端集合可以被清空/新增，造成漏推或对已关闭 socket 发消息。

    本实现用 `asyncio.Lock` 保护所有读写 `_clients` 的 async 入口；
    `has_clients()` 做"非严格但无锁"的读取（因为只用来判断要不要调度，
    错判只会导致多调度一次空 broadcast，不会出错）。
    """

    def __init__(self):
        self._clients: set = set()
        self._loop = None
        # P0-5: 单 asyncio.Lock（进程内事件循环单线程，足够）
        self._lock = asyncio.Lock()

    def attach_loop(self, loop):
        self._loop = loop

    def has_clients(self) -> bool:
        """非严格的快速检查（不拿锁）。仅用于「是否需要调度 broadcast」。"""
        return bool(self._clients)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: str):
        # P0-5: 拿锁后 snapshot 客户端列表，再逐个发送。发送失败的在锁外
        # 清理会有竞态，所以直接在锁内做 discard 即可。
        async with self._lock:
            targets = list(self._clients)
            dead = []
            for ws in targets:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    def broadcast_sync(self, message: str):
        """从同步上下文（engine.step 内）桥接广播到事件循环。"""
        if not self._clients or self._loop is None or self._loop.is_closed():
            return
        # broadcast 内部已带锁，这里无需再同步
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
    """从 engine 实例采集实验元信息（参数化后反映真实拓扑，不读冻结 config）。"""
    return {
        "seed": engine.seed,
        "node_count": engine.node_count,
        "duration": engine.duration,
        "area_size": engine.area_size,
        "adr_enabled": engine.adr_enabled,
        "gateway_cfg": engine.gateway_positions,
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


# P0-4: 用 Engine 显式钩子替换 monkey-patch（语义完全对齐原代码）。
# 原 monkey-patch 顺序：
#   _finalize_current_experiment()  → 读 engine 旧状态 → 写 DB finalize
#   _orig_reset / configure()       → 内部 _build → engine 变为新实验状态
#   _begin_new_experiment()         → 读 engine 新参数 → 写 DB begin
#
# 用引擎钩子后，钩子是在 engine._lock 内部按顺序执行的，不会和 step 并发：
#   pre_reset / pre_configure  → 仍持有旧 engine 状态 → finalize 旧实验
#   (engine 内部 _build)       → 状态切到新实验
#   post_reset / post_configure → 持有新 engine 状态 → begin 新实验
engine.register_pre_reset_hook(_finalize_current_experiment)
engine.register_reset_hook(_begin_new_experiment)
engine.register_pre_configure_hook(_finalize_current_experiment)
engine.register_configure_hook(_begin_new_experiment)


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
    version="5.3.0",
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
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# 托管前端 Dashboard：根路径 / 直接返回 frontend/index.html（同源，免 CORS）
# 必须在 /ws 之后挂载，否则 "/" 挂载会优先拦截 /ws 的 websocket scope。
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
