import asyncio
import os
import uuid as _uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import test_suites, test_cases, test_runs, generation, site_crawl
from app.services.ws_manager import manager as ws_manager

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Agent Test Platform",
        description="Multi-agent LLM-powered platform for generating Playwright test suites",
        version="0.1.0",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(test_suites.router)
    app.include_router(test_cases.router)
    app.include_router(test_runs.router)
    app.include_router(generation.router)
    app.include_router(site_crawl.router)

    # WebSocket endpoint for live test run updates
    @app.websocket("/ws/test-runs/{run_id}")
    async def test_run_websocket(websocket: WebSocket, run_id: str):
        done_event = asyncio.Event()
        await ws_manager.connect(run_id, websocket, done_event)

        # If the run already finished before this client connected, send the
        # current status immediately so the frontend doesn't stay stuck on "Running".
        try:
            from sqlalchemy import select
            from app.database import async_session
            from app.models.test_run import TestRun as _TestRun
            async with async_session() as _db:
                _result = await _db.execute(
                    select(_TestRun).where(_TestRun.id == _uuid.UUID(run_id))
                )
                _run = _result.scalar_one_or_none()
                if _run and _run.status not in ("pending", "running"):
                    await websocket.send_json({
                        "event": "status_change",
                        "status": _run.status,
                    })
                    done_event.set()
        except Exception:
            pass

        async def _drain():
            """Keep draining incoming frames until the client disconnects."""
            try:
                while True:
                    await websocket.receive_text()
            except (WebSocketDisconnect, Exception):
                pass

        recv_task = asyncio.create_task(_drain())
        done_task = asyncio.create_task(done_event.wait())
        try:
            await asyncio.wait([recv_task, done_task], return_when=asyncio.FIRST_COMPLETED)
        finally:
            recv_task.cancel()
            done_task.cancel()
            try:
                await websocket.close()
            except Exception:
                pass
            ws_manager.disconnect(run_id, websocket)

    # WebSocket endpoint for live site crawl progress
    @app.websocket("/ws/crawl/{suite_id}")
    async def crawl_websocket(websocket: WebSocket, suite_id: str):
        done_event = asyncio.Event()
        await ws_manager.connect(suite_id, websocket, done_event)

        async def _drain():
            try:
                while True:
                    await websocket.receive_text()
            except (WebSocketDisconnect, Exception):
                pass

        recv_task = asyncio.create_task(_drain())
        done_task = asyncio.create_task(done_event.wait())
        try:
            await asyncio.wait([recv_task, done_task], return_when=asyncio.FIRST_COMPLETED)
        finally:
            recv_task.cancel()
            done_task.cancel()
            try:
                await websocket.close()
            except Exception:
                pass
            ws_manager.disconnect(suite_id, websocket)

    # Serve artifact files as static content
    artifacts_dir = os.path.abspath(settings.artifacts_dir)
    os.makedirs(artifacts_dir, exist_ok=True)
    app.mount(
        "/artifacts",
        StaticFiles(directory=artifacts_dir),
        name="artifacts",
    )

    @app.get("/api/settings")
    async def get_app_settings():
        return {
            "ollama_model": settings.ollama_model,
            "llm_temperature": settings.llm_temperature,
            "ollama_base_url": settings.ollama_base_url,
            "step_timeout_ms": settings.step_timeout_ms,
            "navigation_timeout_ms": settings.navigation_timeout_ms,
            "execution_timeout_s": settings.execution_timeout_s,
            "max_reverification_attempts": settings.max_reverification_attempts,
        }

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "0.1.0"}

    return app


app = create_app()
