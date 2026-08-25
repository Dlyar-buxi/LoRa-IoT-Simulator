"""FastAPI 入口（Sprint 4.4.1 ~ 4.4.4）。

提供 REST API（/api/*），并托管前端 Dashboard（frontend/ 静态文件）。
Backend 作为 Adapter：包裹冻结的 simulator.Simulation 引擎，并兼任自身 UI 的
Web 服务器（根路径 / 直接提供 frontend/index.html，同源免 CORS）。
路由只读查询，不修改任何冻结模块。

后续 Sprint 计划：连接 SQLite（database.py）与 MQTT（mqtt_client.py）。
"""

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router

# frontend/ 位于项目根（backend 的上一级），与 backend 同属本服务，同源免 CORS
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)

app = FastAPI(
    title="LoRa-IoT-Simulator Backend",
    description="LoRa 智慧农业 / 工业物联网 网络仿真与监控平台 — REST API + Dashboard",
    version="4.4.4",
)

app.include_router(router)

# 托管前端 Dashboard：根路径 / 直接返回 frontend/index.html（同源，免 CORS）
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
