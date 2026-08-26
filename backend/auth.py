"""可选 API Key 认证中间件（P1-6）。

设计目标：**零侵入 Demo 行为，加了配置才生效**。

规则：
- 读取环境变量 ``API_KEY``。为空或未设置 → 整个中间件是 pass-through，
  所有请求放行。保证 README / docker-compose 的默认 demo 体验完全不变。
- 一旦 ``API_KEY`` 非空：
  - ``/api/*`` HTTP 请求必须携带 ``X-API-Key: <value>`` header，否则 401。
  - ``/ws`` WebSocket 握手必须带 URL query ``?token=<value>``（浏览器原生
    WebSocket API 不支持自定义 header，只能走 query），否则 401。
  - 静态资源（非 /api/ 也非 /ws 的路径：/ /index.html /app.js /favicon.ico …）
    始终放行——UI 自己得能加载。

实现选择：
    不使用 FastAPI ``@app.middleware("http")`` / ``BaseHTTPMiddleware``——它们
    只处理 HTTPScope，会漏掉 WebSocketScope。改为直接包装 ``app.__call__``
    的 ASGI 入口，所有 scope 类型（http / websocket / lifespan）都能覆盖。
"""

from __future__ import annotations

import os
import secrets
import urllib.parse as _up
from typing import Optional

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse


# 启动期读一次 env，运行期不重读
_API_KEY: Optional[str] = None
_raw = os.getenv("API_KEY")
if _raw:
    stripped = _raw.strip()
    if stripped:
        _API_KEY = stripped


def api_key_required() -> bool:
    """运行态是否启用了 API Key 校验（供 /api/status 等 UI 提示用）。"""
    return bool(_API_KEY)


def _is_static_or_health(path: str) -> bool:
    """/api/* 和 /ws 之外的所有路径都当作静态资源，永远放行。

    和 main.py 里「先注册 /ws，再 app.mount('/', StaticFiles)」的挂载顺序
    语义对齐：任何不以 /api 或 /ws 开头的路径都会命中 StaticFiles。
    """
    if path == "/api" or path.startswith("/api/"):
        return False
    if path.startswith("/ws"):
        return False
    return True


def _unauth_401(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": detail},
        headers={"WWW-Authenticate": "X-API-Key"},
    )


def _lookup_http_header(headers: list, name_bytes: bytes) -> Optional[str]:
    for n, v in headers:
        if n == name_bytes:
            try:
                return v.decode("latin-1", errors="replace")
            except Exception:  # noqa: BLE001
                return None
    return None


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


class ApiKeyMiddleware:
    """ASGI 级中间件：__call__(scope, receive, send) 覆盖 HTTP + WebSocket。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # 未启用 → 直接短路（零额外分支，几乎零开销）
        if not _API_KEY:
            await self.app(scope, receive, send)
            return

        scope_type = scope.get("type")

        if scope_type == "http":
            path = scope.get("path", "")
            if _is_static_or_health(path):
                await self.app(scope, receive, send)
                return
            key = _lookup_http_header(scope.get("headers", []), b"x-api-key")
            if key is None or not secrets.compare_digest(key, _API_KEY):
                resp = _unauth_401("Missing or invalid X-API-Key header")
                await resp(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        if scope_type == "websocket":
            path = scope.get("path", "")
            if path != "/ws":
                await self.app(scope, receive, send)
                return
            token = _lookup_qs_token(scope.get("query_string", b""))
            if token is None or not secrets.compare_digest(token, _API_KEY):
                resp = _unauth_401(
                    "WebSocket auth requires URL query ?token=<API_KEY>"
                )
                await resp(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        # lifespan / 其他 scope —— 不经认证
        await self.app(scope, receive, send)


def register_auth(app: FastAPI) -> None:
    """把 ApiKeyMiddleware 包在 app.__call__ 外层。

    这是唯一能同时覆盖 HTTP + WebSocket + lifespan 的方式。
    没有 env 时中间件内部第一行就短路 return，完全不影响 demo 行为。
    """
    app.__call__ = ApiKeyMiddleware(app=app.__call__)  # type: ignore[assignment]
