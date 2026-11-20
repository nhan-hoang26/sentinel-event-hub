import logging
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Literal
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from .domain import EventIn
from .store import PayloadConflict, Store

logger = logging.getLogger("uvicorn.error")


def create_app(db_path=None, api_key=None):
    app = FastAPI(title="Sentinel Event Hub", version="1.0.0",
                  description="Synthetic camera event triage. No video inference or emergency dispatch.")
    store = Store(db_path or os.getenv("DATABASE_PATH", "data/sentinel.db"))
    key = api_key if api_key is not None else os.getenv("SENTINEL_API_KEY", "")
    app.state.store = store

    def authenticate(x_api_key: str = Header(default="")):
        if not key:
            raise HTTPException(503, "Set SENTINEL_API_KEY before using the API")
        if not secrets.compare_digest(x_api_key, key):
            raise HTTPException(401, "Invalid API key")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request_id = uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                    request_id, request.method, request.url.path, response.status_code,
                    (time.perf_counter() - start) * 1000)
        return response

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/health")
    def health():
        store.summary()  # Readiness includes a database read.
        return {"status": "ok", "version": "1.0.0"}

    @app.post("/api/events", dependencies=[Depends(authenticate)])
    def ingest(event: EventIn, response: Response):
        try:
            item, duplicate = store.ingest(event)
        except PayloadConflict:
            raise HTTPException(409, "event_id already exists with a different payload") from None
        response.status_code = 200 if duplicate else 201
        return {"event": item, "duplicate": duplicate}

    @app.get("/api/events", dependencies=[Depends(authenticate)])
    def events(severity: Literal["info", "warning", "critical"] | None = None,
               status: Literal["open", "acknowledged"] | None = None,
               limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return store.list_events(severity, status, limit, offset)

    @app.post("/api/events/{event_id}/ack", dependencies=[Depends(authenticate)])
    def acknowledge(event_id: str):
        event = store.acknowledge(event_id)
        if event is None:
            raise HTTPException(404, "Event not found")
        return event

    @app.get("/api/events/{event_id}/audit", dependencies=[Depends(authenticate)])
    def audit(event_id: str):
        return {"items": store.audit(event_id)}

    @app.get("/api/summary", dependencies=[Depends(authenticate)])
    def summary():
        return store.summary()

    return app
