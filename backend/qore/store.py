"""Transactional SQLite records; run/experiment records are immutable via the API."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .workspace import SQLiteWorkspace, initialize_workspace


def now():
    return datetime.now(timezone.utc).isoformat()


def source_hash(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class Store(SQLiteWorkspace):
    def __init__(self, path, owner_id="local"):
        self.path = Path(path)
        self.owner_id = owner_id
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
            # Existing local work is retained under a local-only identity. It
            # is never silently assigned to the first cloud account to log in.
            for table in ("projects", "runs", "experiments"):
                columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                if "owner_id" not in columns:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'")
                db.execute(f"CREATE INDEX IF NOT EXISTS {table}_owner ON {table}(owner_id)")
            initialize_workspace(db)

    def for_owner(self, owner_id):
        if not owner_id:
            raise ValueError("A verified workspace owner is required")
        scoped = object.__new__(Store)
        scoped.path = self.path
        scoped.owner_id = str(owner_id)
        return scoped

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
            return [dict(r) for r in db.execute("SELECT id,name,source,created_at,updated_at FROM projects WHERE owner_id=? ORDER BY updated_at DESC", (self.owner_id,))]

    def project(self, ident):
        with self.connect() as db:
            r = db.execute("SELECT id,name,source,created_at,updated_at FROM projects WHERE id=? AND owner_id=?", (ident, self.owner_id)).fetchone()
            return dict(r) if r else None

    def save_project(self, name, source, ident=None):
        timestamp = now()
        with self.connect() as db:
            if ident:
                result = db.execute("UPDATE projects SET name=?, source=?, updated_at=? WHERE id=? AND owner_id=?",
                                    (name, source, timestamp, ident, self.owner_id))
                if not result.rowcount:
                    return None
            else:
                ident = str(uuid.uuid4())
                db.execute("INSERT INTO projects (id,name,source,created_at,updated_at,owner_id) VALUES (?,?,?,?,?,?)", (ident, name, source, timestamp, timestamp, self.owner_id))
        return self.project(ident)

    def add_run(self, kind, source, project_id, result):
        if project_id and self.project(project_id) is None:
            raise ValueError("Project not found in this workspace")
        record = {**result, "id": str(uuid.uuid4()), "kind": kind, "created_at": now(),
                  "source": source, "source_hash": source_hash(source), "project_id": project_id}
        with self.connect() as db:
            db.execute("INSERT INTO runs (id,project_id,kind,created_at,payload,owner_id) VALUES (?,?,?,?,?,?)",
                       (record["id"], project_id, kind, record["created_at"], json.dumps(record, allow_nan=False), self.owner_id))
        return record

    def run(self, ident):
        with self.connect() as db:
            r = db.execute("SELECT payload FROM runs WHERE id=? AND owner_id=?", (ident, self.owner_id)).fetchone()
            return json.loads(r[0]) if r else None

    def runs(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT payload FROM runs WHERE owner_id=? ORDER BY created_at DESC LIMIT 100", (self.owner_id,))]

    def add_experiment(self, record):
        if record.get("project_id") and self.project(record["project_id"]) is None:
            raise ValueError("Project not found in this workspace")
        record = {**record, "id": str(uuid.uuid4()), "created_at": now()}
        with self.connect() as db:
            db.execute("INSERT INTO experiments (id,project_id,name,created_at,source_hash,payload,owner_id) VALUES (?,?,?,?,?,?,?)", (
                record["id"], record["project_id"], record["name"], record["created_at"],
                record["source_hash"], json.dumps(record, allow_nan=False), self.owner_id))
        return record

    def experiments(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                "SELECT id,project_id,name,created_at,source_hash FROM experiments WHERE owner_id=? ORDER BY created_at DESC", (self.owner_id,))]

    def experiment(self, ident):
        with self.connect() as db:
            r = db.execute("SELECT payload FROM experiments WHERE id=? AND owner_id=?", (ident, self.owner_id)).fetchone()
            return json.loads(r[0]) if r else None
