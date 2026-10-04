"""
api/main.py
────────────
FastAPI application entrypoint.
Mounts all routers, serves media files, handles WebSocket connections,
and exposes the /health endpoint.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Dict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes_alerts    import router as alerts_router
from api.routes_zones     import router as zones_router
from api.routes_cameras   import router as cameras_router
from api.routes_audio     import router as audio_router
from api.routes_analytics import router as analytics_router
from api.routes_reports   import router as reports_router
from api.routes_watchlist import router as watchlist_router
from api.routes_evidence  import router as evidence_router
from api.routes_traffic   import router as traffic_router
from api.websocket_manager import ws_manager
from storage.db import create_tables

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sentryeye.api")

MEDIA_DIR = os.getenv("MEDIA_DIR", "./media")

# ─── Pipeline status registry (updated by pipeline.py) ────────────────────────
# camera_id -> {status, fps, uptime_seconds, last_frame_at}
pipeline_status: Dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("SentryEye API starting up...")
    create_tables()
    logger.info("Database tables verified.")
    yield
    logger.info("SentryEye API shutting down.")


app = FastAPI(
    title="SentryEye API",
    description="Smart Suspicious Activity Detection System & Police Operations Suite",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS (allow React dev server) ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static media files (snapshots + clips) ───────────────────────────────────
os.makedirs(MEDIA_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# ─── Routers ──────────────────────────────────────────────────────────────────
PREFIX = "/api/v1"
app.include_router(alerts_router,    prefix=PREFIX)
app.include_router(zones_router,     prefix=PREFIX)
app.include_router(cameras_router,   prefix=PREFIX)
app.include_router(audio_router,     prefix=PREFIX)
app.include_router(analytics_router, prefix=PREFIX)
app.include_router(reports_router,   prefix=PREFIX)
app.include_router(watchlist_router, prefix=PREFIX)
app.include_router(evidence_router,  prefix=PREFIX)
app.include_router(traffic_router,   prefix=PREFIX)


# ─── WebSocket endpoint ───────────────────────────────────────────────────────
@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — dashboard sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ─── Health endpoint ──────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["system"])
def health():
    """Returns pipeline status per camera — proves FR-5 (continuous monitoring)."""
    now = time.time()
    statuses = []
    for cam_id, info in pipeline_status.items():
        statuses.append({
            "camera_id":       cam_id,
            "status":          info.get("status", "unknown"),
            "fps":             round(info.get("fps", 0), 1),
            "uptime_seconds":  int(now - info.get("started_at", now)),
            "last_frame_at":   info.get("last_frame_at"),
        })
    return {
        "api": "ok",
        "ws_clients": ws_manager.connection_count,
        "cameras": statuses,
    }


@app.get("/api/v1/events", tags=["events"])
def get_events(
    camera_id: str = None,
    rule_type: str = None,
    limit: int = 100,
):
    """Historical incident timeline — delegates to alerts route with no status filter."""
    from storage.db import get_session, Event
    from api.routes_alerts import _to_response
    db = get_session()
    try:
        q = db.query(Event)
        if camera_id: q = q.filter(Event.camera_id == camera_id)
        if rule_type:  q = q.filter(Event.rule_type == rule_type)
        events = q.order_by(Event.timestamp.desc()).limit(limit).all()
        return [_to_response(e) for e in events]
    finally:
        db.close()


@app.get("/", tags=["root"])
def root():
    return {"message": "SentryEye API is running", "docs": "/docs"}
