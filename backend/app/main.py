"""FastAPI アプリ本体。"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Protocol

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.websockets import WebSocketDisconnect, WebSocketState

from .auth import COOKIE_NAME, RateLimiter, SessionStore, token_matches
from .config import Settings
from .security_headers import SecurityHeadersMiddleware, build_csp

log = logging.getLogger("desk")

SLOW_EVERY_TICKS = 10


class MonitorProtocol(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def tick(self) -> dict[str, Any]: ...
    def slow(self) -> dict[str, Any]: ...
    def snapshot(self) -> dict[str, Any]: ...


class LoginBody(BaseModel):
    token: str = Field(min_length=1, max_length=512)


def create_app(
    settings: Settings,
    monitor: MonitorProtocol | None = None,
    tick_interval: float = 1.0,
) -> FastAPI:
    if monitor is None:
        from .monitor import Monitor

        monitor = Monitor(settings)

    sessions = SessionStore(settings.session_ttl_seconds)
    limiter = RateLimiter()
    allowed_origins = set(settings.allowed_origins)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await monitor.start()
        try:
            yield
        finally:
            await monitor.stop()

    app = FastAPI(
        title="IP TEST DESK",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    ws_origins = [f"ws://{h}:{settings.port}" for h in settings.allowed_hosts]
    app.add_middleware(SecurityHeadersMiddleware, csp=build_csp(ws_origins))
    # DNS rebinding 対策（http と websocket の両方に効く）。最も外側に置く。
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    def check_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is not None and origin.rstrip("/") not in allowed_origins:
            raise HTTPException(status_code=403, detail="origin not allowed")

    def require_session(request: Request) -> str:
        sid = request.cookies.get(COOKIE_NAME)
        if not sessions.valid(sid):
            raise HTTPException(status_code=401, detail="unauthorized")
        return sid  # type: ignore[return-value]

    @app.post("/api/login", status_code=204, dependencies=[Depends(check_origin)])
    async def login(body: LoginBody, request: Request, response: Response) -> Response:
        key = request.client.host if request.client else "unknown"
        if not limiter.allow(key):
            raise HTTPException(status_code=429, detail="too many attempts")
        if not token_matches(body.token, settings.token.get_secret_value()):
            limiter.record_failure(key)
            log.warning("login failed from %s", key)
            raise HTTPException(status_code=401, detail="invalid token")
        sid = sessions.create()
        response.set_cookie(
            COOKIE_NAME,
            sid,
            max_age=settings.session_ttl_seconds,
            httponly=True,
            samesite="strict",
            secure=settings.cookie_secure,
            path="/",
        )
        response.status_code = 204
        return response

    @app.post("/api/logout", status_code=204, dependencies=[Depends(check_origin)])
    async def logout(response: Response, sid: str = Depends(require_session)) -> Response:
        sessions.revoke(sid)
        response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="strict")
        response.status_code = 204
        return response

    @app.get("/api/session")
    async def session(request: Request) -> dict[str, bool]:
        return {"authenticated": sessions.valid(request.cookies.get(COOKIE_NAME))}

    @app.get("/api/snapshot", dependencies=[Depends(require_session)])
    async def snapshot() -> dict[str, Any]:
        return monitor.snapshot()

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        origin = (websocket.headers.get("origin") or "").rstrip("/")
        sid = websocket.cookies.get(COOKIE_NAME)
        if origin not in allowed_origins or not sessions.valid(sid):
            # accept 前の close はハンドシェイク拒否（HTTP 403）になる
            await websocket.close(code=1008)
            return
        await websocket.accept()

        async def send(payload: dict[str, Any]) -> None:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False, default=str))

        try:
            await send(monitor.slow())
            await send(monitor.tick())
            n = 0
            while True:
                await asyncio.sleep(tick_interval)
                if not sessions.valid(sid):
                    await websocket.close(code=1008)
                    return
                n += 1
                await send(monitor.tick())
                if n % SLOW_EVERY_TICKS == 0:
                    await send(monitor.slow())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            if websocket.application_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close()
                except RuntimeError:
                    pass

    if settings.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")

    return app
