"""可选 API Key 认证（P1-6）——FastAPI/Starlette 原生兼容方案。

设计目标：**零侵入 Demo 行为，加了配置才生效**。

规则：
- 读取环境变量 ``API_KEY``。为空或未设置 → 所有检查 pass-through，行为零变化。
- 一旦 ``API_KEY`` 非空：
  - ``/api/*`` HTTP 请求必须携带 ``X-API-Key: <value>`` header，否则 401。
  - ``/ws`` WebSocket 握手：若设置了 API_KEY，WS 连接 URL 必须带
    ``?token=<value>``（浏览器原生 WebSocket API 不支持自定义 header）。
  - 静态资源（非 /api/ 且非 /ws）：始终放行。

实现（修复 TestClient 兼容性）：
    先前用「包装 app.__call__」的纯 ASGI 方式，与 Starlette 的 TestClient
    内部 WrapArgsError 冲突（探测 app 风格时 TypeError 逃逸）。
    现改用两条路径：
    1. HTTP：继承 ``BaseHTTPMiddleware``，挂到 ``add_middleware`` 标准链路。
       这是 Starlette 最稳定的 HTTP 中间件插入方式，TestClient 完全支持。
    2. WebSocket：把一个纯函数 ``enforce_ws_token(scope)`` 暴露给 main.py，
       由 main.py 的 ws_endpoint 在 ``await connect()`` 之前显式调用。
       这避免了对 WS 中间件链的任何改写。
"""

from __future__ import annotations

import os
import secrets
import urllib.parse as _up
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import Response as StarletteResponse
from starlette.types import Scope


# 启动期读一次 env，运行期不重读
_API_KEY: Optional[str] = None
_raw = os.getenv("API_KEY")
if _raw:
    stripped = _raw.strip()
    if stripped:
        _API_KEY = stripped


def api_key_required() -> bool:
    """运行态是否启用了 API Key 校验（供 /api/status 提示用）。"""
    return bool(_API_KEY)


def _is_static_or_health(path: str) -> bool:
    """/api/* 之外的所有 HTTP 路径永远放行（StaticFiles、health 等）。"""
    if path == "/api" or path.startswith("/api/"):
        return False
    return True


def _unauth_401(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail},
        headers={"WWW-Authenticate": "X-API-Key"},
    )


def _lookup_qs_token(query_string: bytes) -> Optional[str]:
    if not query_string:
        return None
    for part in query_string.split(b"&"):
        if not part:
            continue
        if part.startswith(b"token="):
            raw = part[len(b"token="):]
            try:
                return _up.unquote_plus(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                return None
    return None


# ---------- HTTP 侧：标准 BaseHTTPMiddleware ----------
class ApiKeyMiddleware(BaseHTTPMiddleware):
    """HTTP-only X-API-Key header 校验。

    静态路径（StaticFiles 挂载域）直接放行；/api/* 非静态请求检查 header。
    API_KEY env 未设置时 dispatch 第一行就短路。
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> StarletteResponse:
        if not _API_KEY:
            return await call_next(request)

        path = request.url.path
        if _is_static_or_health(path):
            return await call_next(request)

        key = request.headers.get("x-api-key")
        if key is None or not secrets.compare_digest(key, _API_KEY):
            return _unauth_401("Missing or invalid X-API-Key header")
        return await call_next(request)


# ---------- WebSocket 侧：纯函数（在 ws_endpoint 内手动调用）----------
class _WsUnauthorized(Exception):
    """信号异常：WS token 校验失败，由调用方转成 401 关闭帧/HTTP 响应。"""


def enforce_ws_token(scope: Scope) -> Optional[JSONResponse]:
    """对 /ws 的 scope 做 token 校验。

    返回值：
    - None：通过，或 API_KEY 未启用（不校验）。
    - JSONResponse：校验失败，调用方应当 await resp(scope, receive, send)
      来给客户端返回 401 并关闭握手。
    """
    if not _API_KEY:
        return None
    # scope["path"] 一定是 "/ws"（main.py 的路由），但我们不 hardcode——
    # 如果 scope 不是 websocket 也放过，让 FastAPI 自己处理。
    if scope.get("type") != "websocket":
        return None
    token = _lookup_qs_token(scope.get("query_string", b""))
    if token is None or not secrets.compare_digest(token, _API_KEY):
        return _unauth_401("WebSocket auth requires URL query ?token=<API_KEY>")
    return None


# ---------- 便捷注册函数 ----------
def register_auth(app: FastAPI) -> None:
    """注册 HTTP 中间件（标准 add_middleware 链路）。

    WS 校验不在此处做——由 main.py 在 @app.websocket("/ws") 端点内部
    显式调用 ``enforce_ws_token(scope)`` 来完成。
    """
    # 只注册 HTTP 中间件；WS 内联校验
    app.add_middleware(ApiKeyMiddleware)
