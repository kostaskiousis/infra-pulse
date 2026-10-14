"""FastAPI application and read-only JSON endpoints."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .config import Settings, load_targets
from .monitor import Monitor
from .storage import Storage

BASE = Path(__file__).resolve().parent
settings = Settings.from_env()
targets = load_targets(settings.targets_path)
storage = Storage(settings.db_path)
monitor = Monitor(settings, targets, storage)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await storage.initialize()
    task = asyncio.create_task(monitor.run(), name="infrapulse-monitor")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="InfraPulse", version="1.0.0", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=BASE / "static"), name="assets")


@app.get("/", include_in_schema=False)
async def dashboard():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/health")
async def health():
    return {
        "status": "ok" if monitor.last_check is not None and monitor.last_error is None else "starting_or_degraded",
        "last_check": monitor.last_check,
        "poll_error": monitor.last_error,
    }


@app.get("/api/overview")
async def overview():
    return monitor.overview()


@app.get("/api/history")
async def history(host: str | None = None, limit: int = Query(default=80, ge=1, le=500)):
    if host is not None and host not in {target.host for target in targets}:
        raise HTTPException(status_code=404, detail="Target not configured")
    return {"series": "device" if host else "system", "samples": await storage.recent_history(host, limit)}


@app.get("/api/events")
async def events(limit: int = Query(default=20, ge=1, le=100)):
    return {"events": await storage.recent_events(limit)}


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
