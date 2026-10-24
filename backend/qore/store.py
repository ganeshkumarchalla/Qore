"""Transactional SQLite records; run/experiment records are immutable via the API."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def source_hash(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, project_id TEXT, kind TEXT NOT NULL,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY, project_id TEXT, name TEXT NOT NULL,
                    created_at TEXT NOT NULL, source_hash TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS runs_project ON runs(project_id);
                CREATE INDEX IF NOT EXISTS experiments_project ON experiments(project_id);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def projects(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY updated_at DESC")]

    def project(self, ident):
        with self.connect() as db:
            r = db.execute("SELECT * FROM projects WHERE id=?", (ident,)).fetchone()
            return dict(r) if r else None

    def save_project(self, name, source, ident=None):
        timestamp = now()
        with self.connect() as db:
            if ident:
                result = db.execute("UPDATE projects SET name=?, source=?, updated_at=? WHERE id=?",
                                    (name, source, timestamp, ident))
                if not result.rowcount:
                    return None
            else:
                ident = str(uuid.uuid4())
                db.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (ident, name, source, timestamp, timestamp))
        return self.project(ident)

    def add_run(self, kind, source, project_id, result):
        record = {**result, "id": str(uuid.uuid4()), "kind": kind, "created_at": now(),
                  "source": source, "source_hash": source_hash(source), "project_id": project_id}
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?)",
                       (record["id"], project_id, kind, record["created_at"], json.dumps(record, allow_nan=False)))
        return record

    def run(self, ident):
        with self.connect() as db:
            r = db.execute("SELECT payload FROM runs WHERE id=?", (ident,)).fetchone()
            return json.loads(r[0]) if r else None

    def runs(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT payload FROM runs ORDER BY created_at DESC LIMIT 100")]

    def add_experiment(self, record):
        record = {**record, "id": str(uuid.uuid4()), "created_at": now()}
        with self.connect() as db:
            db.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?)", (
                record["id"], record["project_id"], record["name"], record["created_at"],
                record["source_hash"], json.dumps(record, allow_nan=False)))
        return record

    def experiments(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,project_id,name,created_at,source_hash FROM experiments ORDER BY created_at DESC")]

    def experiment(self, ident):
        with self.connect() as db:
            r = db.execute("SELECT payload FROM experiments WHERE id=?", (ident,)).fetchone()
            return json.loads(r[0]) if r else None
