"""SQLite transactions enforce idempotency across concurrent API requests."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .domain import EventIn, severity


class PayloadConflict(Exception):
    pass


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, camera_id TEXT NOT NULL,
                kind TEXT NOT NULL, confidence REAL NOT NULL, zone TEXT NOT NULL,
                occurred_at TEXT NOT NULL, received_at TEXT NOT NULL,
                severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
                acknowledged_at TEXT, payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_events_received ON events(received_at DESC);
            CREATE INDEX IF NOT EXISTS ix_events_severity ON events(severity);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, event_id TEXT NOT NULL,
                action TEXT NOT NULL, created_at TEXT NOT NULL
            );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def public(row):
        return {k: row[k] for k in row.keys() if k != "payload"}

    def ingest(self, event: EventIn):
        payload = event.model_dump_json()
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM events WHERE event_id=?", (event.event_id,)).fetchone()
            if row:
                if json.loads(row["payload"]) != json.loads(payload):
                    raise PayloadConflict()
                return self.public(row), True
            db.execute("""INSERT INTO events
                (event_id,camera_id,kind,confidence,zone,occurred_at,received_at,severity,payload)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (event.event_id, event.camera_id, event.kind.value, event.confidence,
                 event.zone, event.occurred_at.isoformat(), now, severity(event), payload))
            db.execute("INSERT INTO audit(event_id,action,created_at) VALUES (?,?,?)",
                       (event.event_id, "ingested", now))
            row = db.execute("SELECT * FROM events WHERE event_id=?", (event.event_id,)).fetchone()
            return self.public(row), False

    def list_events(self, level=None, status=None, limit=50, offset=0):
        clauses, args = [], []
        for column, value in (("severity", level), ("status", status)):
            if value:
                clauses.append(f"{column}=?")
                args.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) FROM events" + where, args).fetchone()[0]
            rows = db.execute("SELECT * FROM events" + where +
                              " ORDER BY received_at DESC, event_id LIMIT ? OFFSET ?",
                              [*args, limit, offset]).fetchall()
            return {"items": [self.public(r) for r in rows], "total": total,
                    "limit": limit, "offset": offset}

    def acknowledge(self, event_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                return None
            if row["status"] == "open":
                now = datetime.now(timezone.utc).isoformat()
                db.execute("UPDATE events SET status='acknowledged', acknowledged_at=? WHERE event_id=?",
                           (now, event_id))
                db.execute("INSERT INTO audit(event_id,action,created_at) VALUES (?,?,?)",
                           (event_id, "acknowledged", now))
            return self.public(db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone())

    def summary(self):
        with self.connect() as db:
            return dict(db.execute("""SELECT COUNT(*) AS total,
                COALESCE(SUM(status='open'),0) AS open,
                COALESCE(SUM(status='open' AND severity='critical'),0) AS critical_open,
                COUNT(DISTINCT camera_id) AS cameras FROM events""").fetchone())

    def audit(self, event_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT action,created_at FROM audit WHERE event_id=? ORDER BY id", (event_id,))]
