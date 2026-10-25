"""Durable editable files, independent from immutable quantum evidence records."""

from __future__ import annotations

import asyncio
import sqlite3
import unicodedata
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .runtime import JobError


RETENTION_HOURS = 48
MAX_ENTRIES = 1000
MAX_WORKSPACE_BYTES = 16 * 1024 * 1024
KINDS = {"python", "qasm", "json", "markdown"}


def clock():
    return datetime.now(timezone.utc)


def valid_path(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    parts = value.split("/")
    if (not value or len(value) > 512 or value != value.strip()
            or any(char in value for char in '\\:*?"<>|')
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(not part or part in {".", ".."} or len(part) > 100 or part != part.strip() for part in parts)):
        raise ValueError("Use a relative workspace path with safe slash-separated names (512 characters maximum).")
    return value


def valid_ident(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise JobError("workspace_not_found", "Workspace item not found.", status=404) from None


def problem(code, message, status=409):
    raise JobError(code, message, status=status)


def initialize_workspace(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS workspace_entries (
          id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, path TEXT NOT NULL,
          entry_type TEXT NOT NULL CHECK(entry_type IN ('file','folder')),
          source TEXT NOT NULL DEFAULT '', kind TEXT,
          version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          deleted_at TEXT, expires_at TEXT, trash_batch_id TEXT,
          CHECK((deleted_at IS NULL AND expires_at IS NULL AND trash_batch_id IS NULL)
            OR (deleted_at IS NOT NULL AND expires_at IS NOT NULL AND trash_batch_id IS NOT NULL)),
          CHECK((entry_type='folder' AND kind IS NULL AND source='')
            OR (entry_type='file' AND kind IN ('python','qasm','json','markdown')))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS workspace_active_path ON workspace_entries(owner_id,path) WHERE deleted_at IS NULL;
        CREATE INDEX IF NOT EXISTS workspace_owner ON workspace_entries(owner_id,updated_at);
        CREATE INDEX IF NOT EXISTS workspace_expiry ON workspace_entries(expires_at) WHERE expires_at IS NOT NULL;
        CREATE TABLE IF NOT EXISTS workspace_state (
          owner_id TEXT PRIMARY KEY, active_file_id TEXT, last_deleted_id TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workspace_tombstones (
          id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, removed_at TEXT NOT NULL
        );
    """)


def entry_dto(entry):
    result = {key: entry[key] for key in ("id", "path", "source", "kind", "version", "created_at", "updated_at", "deleted_at", "expires_at")}
    result.update(name=entry["path"].rsplit("/", 1)[-1], type=entry["entry_type"])
    return result


class SQLiteWorkspace:
    """Store mixin: every mutation is one write transaction scoped to its owner."""

    def _workspace_purge(self, db, timestamp):
        db.execute("INSERT OR IGNORE INTO workspace_tombstones(id,owner_id,removed_at) SELECT id,owner_id,? FROM workspace_entries WHERE owner_id=? AND expires_at IS NOT NULL AND expires_at<=?", (timestamp, self.owner_id, timestamp))
        removed = db.execute("DELETE FROM workspace_entries WHERE owner_id=? AND expires_at IS NOT NULL AND expires_at<=?", (self.owner_id, timestamp)).rowcount
        db.execute("""UPDATE workspace_state SET
            active_file_id=CASE WHEN EXISTS(SELECT 1 FROM workspace_entries e WHERE e.owner_id=? AND e.id=active_file_id AND e.deleted_at IS NULL AND e.entry_type='file') THEN active_file_id ELSE NULL END,
            last_deleted_id=CASE WHEN EXISTS(SELECT 1 FROM workspace_entries e WHERE e.owner_id=? AND e.id=last_deleted_id AND e.deleted_at IS NOT NULL) THEN last_deleted_id ELSE NULL END
            WHERE owner_id=?""", (self.owner_id, self.owner_id, self.owner_id))
        return removed

    def workspace_purge_all(self):
        """Host maintenance: expired trash only; never projects/runs/active files."""
        with self.connect() as db:
            timestamp = clock().isoformat()
            db.execute("INSERT OR IGNORE INTO workspace_tombstones(id,owner_id,removed_at) SELECT id,owner_id,? FROM workspace_entries WHERE expires_at IS NOT NULL AND expires_at<=?", (timestamp, timestamp))
            return db.execute("DELETE FROM workspace_entries WHERE expires_at IS NOT NULL AND expires_at<=?", (timestamp,)).rowcount

    def _workspace_rows(self, db):
        return [dict(row) for row in db.execute("SELECT * FROM workspace_entries WHERE owner_id=? ORDER BY path,id", (self.owner_id,))]

    def _workspace_snapshot(self, db, timestamp):
        entries = self._workspace_rows(db)
        state = db.execute("SELECT active_file_id,last_deleted_id FROM workspace_state WHERE owner_id=?", (self.owner_id,)).fetchone()
        files = [entry_dto(row) for row in entries if row["deleted_at"] is None and row["entry_type"] == "file"]
        folders = [entry_dto(row) for row in entries if row["deleted_at"] is None and row["entry_type"] == "folder"]
        trash = [entry_dto(row) for row in entries if row["deleted_at"] is not None and row["expires_at"] > timestamp]
        active = state["active_file_id"] if state and any(row["id"] == state["active_file_id"] for row in files) else None
        last = state["last_deleted_id"] if state and any(row["id"] == state["last_deleted_id"] for row in trash) else None
        return {"files": files, "folders": folders, "trash": trash, "active_file_id": active,
                "last_deleted_id": last, "retention_hours": RETENTION_HOURS, "server_time": timestamp}

    def workspace_snapshot(self):
        with self.connect() as db:
            timestamp = clock().isoformat()
            self._workspace_purge(db, timestamp)
            return self._workspace_snapshot(db, timestamp)

    def _workspace_bump_parents(self, db, paths, excluded, timestamp):
        parents = {"/".join(path.split("/")[:index]) for path in paths for index in range(1, len(path.split("/")))}
        for path in parents:
            row = db.execute("SELECT id FROM workspace_entries WHERE owner_id=? AND path=? AND entry_type='folder' AND deleted_at IS NULL", (self.owner_id, path)).fetchone()
            if row and row["id"] not in excluded:
                db.execute("UPDATE workspace_entries SET version=version+1,updated_at=? WHERE id=? AND owner_id=?", (timestamp, row["id"], self.owner_id))

    def workspace_put(self, ident, entry_type, path, source, kind, expected_version=0):
        ident = valid_ident(ident)
        try:
            path = valid_path(path)
        except ValueError:
            problem("invalid_workspace_path", "The workspace path is invalid.", 422)
        if entry_type not in {"file", "folder"} or (entry_type == "file" and kind not in KINDS):
            problem("invalid_workspace_kind", "The workspace file kind is invalid.", 422)
        if not isinstance(source, str) or len(source.encode("utf-8")) > 32768:
            problem("workspace_source_too_large", "Files are limited to 32768 UTF-8 bytes.", 422)
        if entry_type == "folder":
            source, kind = "", None
        if type(expected_version) is not int or expected_version < 0:
            problem("invalid_workspace_version", "The workspace version is invalid.", 422)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            timestamp = clock().isoformat()
            self._workspace_purge(db, timestamp)
            rows = self._workspace_rows(db)
            previous = next((row for row in rows if row["id"] == ident), None)
            if previous:
                if previous["entry_type"] != entry_type:
                    problem("workspace_not_found", "Workspace item not found.", 404)
                if previous["deleted_at"] is not None:
                    problem("workspace_deleted", "This item is in Trash. Restore it before editing.")
                if previous["path"] == path and previous["source"] == source and previous["kind"] == kind:
                    return entry_dto(previous)
                if previous["version"] != expected_version:
                    problem("workspace_version_conflict", "This item changed in another session. Reload its latest version before saving.")
            elif expected_version != 0:
                problem("workspace_not_found", "Workspace item not found.", 404)
            if not previous and db.execute("SELECT 1 FROM workspace_entries WHERE id=?", (ident,)).fetchone():
                problem("workspace_not_found", "Workspace item not found.", 404)
            tombstone = db.execute("SELECT owner_id FROM workspace_tombstones WHERE id=?", (ident,)).fetchone() if not previous else None
            if tombstone:
                problem("workspace_deleted" if tombstone["owner_id"] == self.owner_id else "workspace_not_found",
                        "This item was permanently removed. Create a new file to continue." if tombstone["owner_id"] == self.owner_id else "Workspace item not found.",
                        409 if tombstone["owner_id"] == self.owner_id else 404)
            if not previous and len(rows) >= MAX_ENTRIES:
                problem("workspace_full", "The workspace item limit has been reached. Empty expired Trash or remove unused files.")
            if sum(len(row["source"].encode("utf-8")) for row in rows) - len((previous or {}).get("source", "").encode("utf-8")) + len(source.encode("utf-8")) > MAX_WORKSPACE_BYTES:
                problem("workspace_full", "The private workspace storage limit has been reached.")
            active = [row for row in rows if row["deleted_at"] is None]
            moving = [previous] if previous else []
            if previous and entry_type == "folder" and previous["path"] != path:
                if path.startswith(previous["path"] + "/"):
                    problem("workspace_path_conflict", "A folder cannot be moved inside itself.")
                moving += [row for row in active if row["path"].startswith(previous["path"] + "/")]
            moving_ids = {row["id"] for row in moving}
            destinations = {row["id"]: path + row["path"][len(previous["path"]):] for row in moving} if previous else {ident: path}
            try:
                for value in destinations.values():
                    valid_path(value)
            except ValueError:
                problem("invalid_workspace_path", "A descendant path would exceed workspace path limits.", 422)
            final = [(row["id"], row["path"], row["entry_type"]) for row in active if row["id"] not in moving_ids]
            final += [(row["id"], destinations[row["id"]], row["entry_type"]) for row in moving] if previous else [(ident, path, entry_type)]
            paths = [row[1] for row in final]
            if len(paths) != len(set(paths)) or any(other[1].startswith(row[1] + "/") for row in final if row[2] == "file" for other in final if other[0] != row[0]):
                problem("workspace_path_conflict", "A file or folder already occupies the destination path.")
            try:
                if previous:
                    temporary = "__qore_move_" + uuid4().hex + "/"
                    for row in moving:
                        db.execute("UPDATE workspace_entries SET path=? WHERE id=? AND owner_id=?", (temporary + row["id"], row["id"], self.owner_id))
                    for row in moving:
                        db.execute("UPDATE workspace_entries SET path=?,version=version+1,updated_at=? WHERE id=? AND owner_id=?", (destinations[row["id"]], timestamp, row["id"], self.owner_id))
                    db.execute("UPDATE workspace_entries SET source=?,kind=? WHERE id=? AND owner_id=?", (source, kind, ident, self.owner_id))
                else:
                    db.execute("INSERT INTO workspace_entries(id,owner_id,path,entry_type,source,kind,version,created_at,updated_at) VALUES (?,?,?,?,?,?,1,?,?)", (ident, self.owner_id, path, entry_type, source, kind, timestamp, timestamp))
                self._workspace_bump_parents(db, [path] + ([previous["path"]] if previous else []), moving_ids | {ident}, timestamp)
            except sqlite3.IntegrityError:
                problem("workspace_path_conflict", "A file or folder already occupies the destination path.")
            return entry_dto(dict(db.execute("SELECT * FROM workspace_entries WHERE id=? AND owner_id=?", (ident, self.owner_id)).fetchone()))

    def workspace_delete(self, ident, entry_type, expected_version):
        ident = valid_ident(ident)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            timestamp = clock()
            self._workspace_purge(db, timestamp.isoformat())
            rows = self._workspace_rows(db)
            target = next((row for row in rows if row["id"] == ident and row["entry_type"] == entry_type), None)
            if not target:
                problem("workspace_not_found", "Workspace item not found.", 404)
            if target["deleted_at"] is not None:
                return self._workspace_snapshot(db, timestamp.isoformat())
            if target["version"] != expected_version:
                problem("workspace_version_conflict", "This item changed in another session. Reload before deleting.")
            affected = [row for row in rows if row["deleted_at"] is None and (row["id"] == ident or (entry_type == "folder" and row["path"].startswith(target["path"] + "/")))]
            for row in affected:
                db.execute("UPDATE workspace_entries SET deleted_at=?,expires_at=?,trash_batch_id=?,updated_at=?,version=version+1 WHERE id=? AND owner_id=?", (timestamp.isoformat(), (timestamp + timedelta(hours=RETENTION_HOURS)).isoformat(), ident, timestamp.isoformat(), row["id"], self.owner_id))
            db.execute("INSERT INTO workspace_state(owner_id,last_deleted_id,updated_at) VALUES (?,?,?) ON CONFLICT(owner_id) DO UPDATE SET last_deleted_id=excluded.last_deleted_id,updated_at=excluded.updated_at", (self.owner_id, ident, timestamp.isoformat()))
            self._workspace_bump_parents(db, [target["path"]], {row["id"] for row in affected}, timestamp.isoformat())
            self._workspace_purge(db, timestamp.isoformat())
            return self._workspace_snapshot(db, timestamp.isoformat())

    def _workspace_restore(self, db, ident, entry_type, timestamp):
        rows = self._workspace_rows(db)
        target = next((row for row in rows if row["id"] == ident and row["entry_type"] == entry_type), None)
        if not target:
            problem("workspace_not_found", "This item is unavailable or its Trash retention period has expired.", 404)
        if target["deleted_at"] is None:
            return self._workspace_snapshot(db, timestamp)
        restoring = [row for row in rows if row["deleted_at"] is not None and (row["id"] == ident or (entry_type == "folder" and row["trash_batch_id"] == ident))]
        final = [row for row in rows if row["deleted_at"] is None] + restoring
        paths = [row["path"] for row in final]
        if len(paths) != len(set(paths)) or any(other["path"].startswith(row["path"] + "/") for row in final if row["entry_type"] == "file" for other in final if other["id"] != row["id"]):
            problem("workspace_path_conflict", "A destination is occupied. Rename the active item before restoring this deletion.")
        for row in restoring:
            db.execute("UPDATE workspace_entries SET deleted_at=NULL,expires_at=NULL,trash_batch_id=NULL,updated_at=?,version=version+1 WHERE id=? AND owner_id=?", (timestamp, row["id"], self.owner_id))
        db.execute("UPDATE workspace_state SET last_deleted_id=CASE WHEN last_deleted_id=? THEN NULL ELSE last_deleted_id END,updated_at=? WHERE owner_id=?", (ident, timestamp, self.owner_id))
        self._workspace_bump_parents(db, [target["path"]], {row["id"] for row in restoring}, timestamp)
        return self._workspace_snapshot(db, timestamp)

    def workspace_restore(self, ident, entry_type):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            timestamp = clock().isoformat()
            self._workspace_purge(db, timestamp)
            return self._workspace_restore(db, valid_ident(ident), entry_type, timestamp)

    def workspace_state(self, active_file_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            timestamp = clock().isoformat()
            self._workspace_purge(db, timestamp)
            if active_file_id is not None:
                active_file_id = valid_ident(active_file_id)
                if not db.execute("SELECT 1 FROM workspace_entries WHERE id=? AND owner_id=? AND entry_type='file' AND deleted_at IS NULL", (active_file_id, self.owner_id)).fetchone():
                    problem("workspace_not_found", "Active workspace file not found.", 404)
            db.execute("INSERT INTO workspace_state(owner_id,active_file_id,updated_at) VALUES (?,?,?) ON CONFLICT(owner_id) DO UPDATE SET active_file_id=excluded.active_file_id,updated_at=excluded.updated_at", (self.owner_id, active_file_id, timestamp))
            return self._workspace_snapshot(db, timestamp)

    def workspace_undo(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            timestamp = clock().isoformat()
            self._workspace_purge(db, timestamp)
            state = db.execute("SELECT last_deleted_id FROM workspace_state WHERE owner_id=?", (self.owner_id,)).fetchone()
            target = db.execute("SELECT entry_type FROM workspace_entries WHERE id=? AND owner_id=?", (state["last_deleted_id"], self.owner_id)).fetchone() if state and state["last_deleted_id"] else None
            return self._workspace_restore(db, state["last_deleted_id"], target["entry_type"], timestamp) if target else self._workspace_snapshot(db, timestamp)


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FolderInput(WorkspaceModel):
    path: str = Field(min_length=1, max_length=512)
    expected_version: int = Field(default=0, ge=0, strict=True)

    @field_validator("path")
    @classmethod
    def safe_path(cls, value):
        return valid_path(value)


class FileInput(FolderInput):
    source: str = Field(default="", max_length=32768)
    kind: Literal["python", "qasm", "json", "markdown"]

    @field_validator("source")
    @classmethod
    def source_size(cls, value):
        if "\x00" in value:
            raise ValueError("Workspace files must contain plain text without null bytes.")
        if len(value.encode("utf-8")) > 32768:
            raise ValueError("Files are limited to 32768 UTF-8 bytes.")
        return value


class DeleteInput(WorkspaceModel):
    expected_version: int = Field(ge=1, strict=True)


class StateInput(WorkspaceModel):
    active_file_id: UUID | None


def register_workspace(application: FastAPI, storage):
    """Register routes against main's async owner-scoped storage(method,*args)."""
    router = APIRouter(prefix="/api/workspace")

    @router.get("")
    async def workspace():
        return await storage("workspace_snapshot")

    @router.get("/trash")
    async def trash():
        result = await storage("workspace_snapshot")
        return {key: result[key] for key in ("trash", "retention_hours", "server_time")}

    @router.put("/files/{ident}")
    async def put_file(ident: UUID, body: FileInput):
        return await storage("workspace_put", str(ident), "file", body.path, body.source, body.kind, body.expected_version)

    @router.put("/folders/{ident}")
    async def put_folder(ident: UUID, body: FolderInput):
        return await storage("workspace_put", str(ident), "folder", body.path, "", None, body.expected_version)

    @router.delete("/files/{ident}")
    async def delete_file(ident: UUID, body: DeleteInput):
        return await storage("workspace_delete", str(ident), "file", body.expected_version)

    @router.delete("/folders/{ident}")
    async def delete_folder(ident: UUID, body: DeleteInput):
        return await storage("workspace_delete", str(ident), "folder", body.expected_version)

    @router.post("/files/{ident}/restore")
    async def restore_file(ident: UUID):
        return await storage("workspace_restore", str(ident), "file")

    @router.post("/folders/{ident}/restore")
    async def restore_folder(ident: UUID):
        return await storage("workspace_restore", str(ident), "folder")

    @router.post("/undo")
    async def undo():
        return await storage("workspace_undo")

    @router.patch("/state")
    async def state(body: StateInput):
        return await storage("workspace_state", str(body.active_file_id) if body.active_file_id else None)

    application.include_router(router)
    previous_lifespan = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with previous_lifespan(app):
            async def purge_loop():
                while True:
                    local = getattr(app.state, "store", None)
                    if local is not None:
                        try:
                            await asyncio.to_thread(local.workspace_purge_all)
                            app.state.workspace_cleanup_status = "ok"
                        except sqlite3.Error:
                            app.state.workspace_cleanup_status = "retry_pending"
                    await asyncio.sleep(300)
            task = asyncio.create_task(purge_loop())
            try:
                yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    application.router.lifespan_context = lifespan
