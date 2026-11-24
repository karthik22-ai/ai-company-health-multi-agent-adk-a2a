"""FastAPI application: REST + WebSocket/SSE bridge to the 3D UI, and every agent served over A2A."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from hq.a2a.host import mount_a2a_agents
from hq.api.bridge import UIBridge
from hq.api.routes.agents import router
from hq.api.routes.company import router as company_router
from hq.core.clock import CompanyRunner
from hq.core.config import Settings, get_settings
from hq.core.services import Services, build_services

log = logging.getLogger("hq.app")


class A2AAuthMiddleware:
    """Pure ASGI middleware: protects /a2a/* with the same bearer token as the REST API (when a token is configured)."""

    def __init__(self, app: Any, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/a2a/") and ".well-known" not in scope["path"]:
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            if headers.get("authorization") != f"Bearer {self.token}":
                await JSONResponse({"detail": "missing or invalid token"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc: Services = build_services(settings)
        app.state.svc = svc
        app.state.bridge = UIBridge(svc)
        async with AsyncExitStack() as stack:
            svc.app, svc.a2a_stack = app, stack
            svc.cards = await mount_a2a_agents(app, svc.runtime, settings, stack)
            if settings.a2a_transport == "asgi":
                svc.peers.bind_asgi(app)
            else:
                svc.peers.bind_http()
            await asyncio.to_thread(svc.company.ensure_history, settings.sim_history_days)
            svc.runner = CompanyRunner(svc)
            from hq.town.loop import TownLoop
            svc.town_loop = TownLoop(svc)
            svc.town_loop.start()
            if settings.sim_autostart:
                svc.runner.start()
            if settings.auth_token and svc.peers.http is not None:
                svc.peers.http.headers["Authorization"] = f"Bearer {settings.auth_token}"
            log.info("AI Company HQ backend ready · LLM: %s · %d agents over A2A", settings.llm_label, len(svc.cards))
            try:
                yield
            finally:
                await svc.runner.pause()
                await svc.peers.aclose()
                svc.company.close()

    app = FastAPI(title="AI Company HQ backend", version="0.1.0", lifespan=lifespan)
    if settings.auth_token:
        app.add_middleware(A2AAuthMiddleware, token=settings.auth_token)
    app.include_router(router)
    app.include_router(company_router)
    from hq.api.routes.work import router as work_router
    app.include_router(work_router)
    from hq.api.routes.quality import router as quality_router
    app.include_router(quality_router)

    @app.get("/health")
    async def health(request: Request):
        s: Services = request.app.state.svc
        return {"status": "ok", "llm": s.settings.llm_label, "agents": len(s.world.agents), "a2a_agents": len(s.cards), "runs": len(s.workflows.runs),
                "company_date": s.company.today.isoformat(), "clock": s.runner.state()}

    @app.get("/")
    async def index(request: Request):
        scheme = "wss" if request.url.scheme == "https" else "ws"
        ws = f"{scheme}://{request.url.netloc}/ws"
        if settings.auth_token:
            ws += f"?token={settings.auth_token}"
        return RedirectResponse(f"/ui/?ws={ws}")

    @app.get("/ui")
    async def ui_redirect(request: Request):
        return RedirectResponse("/ui/" + (f"?{request.url.query}" if request.url.query else ""))

    @app.get("/ui/")
    async def ui():
        index = settings.ui_dir / "index.html"
        if not index.exists():
            return JSONResponse({"detail": f"UI not found at {settings.ui_dir}"}, status_code=404)
        return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})

    @app.get("/ui/app.js")
    async def ui_js():
        """The frontend modules (frontend/js/*.js) joined in manifest order into one classic script, so they share one global scope."""
        js = settings.ui_dir / "js"
        order = json.loads((js / "manifest.json").read_text())["order"]
        body = "\n".join((js / f).read_text(encoding="utf-8") for f in order)
        return Response(body, media_type="application/javascript", headers={"Cache-Control": "no-cache"})

    for sub in ("css", "js"):                      # stylesheets and (for debugging) the individual modules
        if (settings.ui_dir / sub).is_dir():
            app.mount(f"/ui/{sub}", StaticFiles(directory=settings.ui_dir / sub), name=f"ui-{sub}")

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        s: Services = websocket.app.state.svc
        bridge: UIBridge = websocket.app.state.bridge
        if settings.auth_token and websocket.query_params.get("token") != settings.auth_token:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        q = s.bus.subscribe()
        try:
            for cmd in s.world.resync_commands():           # bring a (re)loaded UI up to date
                await websocket.send_text(json.dumps(cmd))

            async def pump() -> None:
                while True:
                    await websocket.send_text(json.dumps(await q.get()))

            pump_task = asyncio.create_task(pump())
            try:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        bridge.handle(json.loads(raw))
                    except json.JSONDecodeError:
                        log.warning("ignored non-JSON message from UI")
            finally:
                pump_task.cancel()
        except WebSocketDisconnect:
            pass
        finally:
            s.bus.unsubscribe(q)

    return app


