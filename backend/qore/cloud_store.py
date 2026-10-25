"""Owner-scoped persistence through Supabase PostgREST and its RLS policies.

Only a publishable key and the verified user's short-lived token are used.
This module never bypasses row security with a privileged service-role key.
"""
import uuid

import httpx

from .runtime import JobError
from .store import now, source_hash


WORKSPACE_ERRORS = {
    "workspace_not_found": (404, "Workspace item not found or its Trash retention period has expired."),
    "workspace_deleted": (409, "This item was deleted. Restore it before editing, or create a new file if its retention period has expired."),
    "workspace_version_conflict": (409, "This item changed in another session. Reload its latest version before saving."),
    "workspace_path_conflict": (409, "A file or folder already occupies the destination path."),
    "invalid_workspace_path": (422, "The workspace path is invalid."),
    "invalid_workspace_kind": (422, "The workspace file kind is invalid."),
    "invalid_workspace_version": (422, "The workspace version is invalid."),
    "workspace_source_too_large": (422, "Files are limited to 32768 UTF-8 bytes."),
    "workspace_full": (409, "The private workspace storage limit has been reached."),
    "authentication_required": (401, "Sign in to open your private workspace."),
    "invalid_workspace_operation": (422, "The workspace request is invalid."),
}


class CloudStore:
    def __init__(self, url, publishable_key, owner_id, access_token, transport=None):
        if not owner_id or not access_token:
            raise JobError("authentication_required", "Sign in to open your private workspace.", status=401)
        self.url = url.rstrip("/") + "/rest/v1/"
        self.key = publishable_key
        self.owner_id = str(uuid.UUID(owner_id))
        self.access_token = access_token
        self.transport = transport

    def _request(self, method, table, *, params=None, body=None):
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.access_token}",
                   "Prefer": "return=representation", "Content-Type": "application/json"}
        query = {"owner_id": f"eq.{self.owner_id}", **(params or {})}
        try:
            with httpx.Client(timeout=httpx.Timeout(15, connect=5), transport=self.transport, trust_env=False) as client:
                response = client.request(method, self.url + table, headers=headers, params=query, json=body)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, list):
                raise ValueError("Invalid persistence response")
            return result
        except (httpx.HTTPError, ValueError, TypeError):
            raise JobError("storage_unavailable", "Your private workspace could not be reached. Please retry.", status=503) from None

    @staticmethod
    def _id(ident):
        try:
            return str(uuid.UUID(str(ident)))
        except (ValueError, TypeError, AttributeError):
            return None

    def projects(self):
        return self._request("GET", "qore_projects", params={"select": "id,name,source,created_at,updated_at", "order": "updated_at.desc", "limit": "1000"})

    def project(self, ident):
        ident = self._id(ident)
        if not ident:
            return None
        rows = self._request("GET", "qore_projects", params={"id": f"eq.{ident}", "select": "id,name,source,created_at,updated_at", "limit": "1"})
        return rows[0] if rows else None

    def save_project(self, name, source, ident=None):
        timestamp = now()
        payload = {"name": name, "source": source, "updated_at": timestamp}
        if ident:
            ident = self._id(ident)
            if not ident:
                return None
            rows = self._request("PATCH", "qore_projects", params={"id": f"eq.{ident}"}, body=payload)
        else:
            payload.update(id=str(uuid.uuid4()), owner_id=self.owner_id, created_at=timestamp)
            rows = self._request("POST", "qore_projects", body=payload)
        return {k: v for k, v in rows[0].items() if k != "owner_id"} if rows else None

    def add_run(self, kind, source, project_id, result):
        record = {**result, "id": str(uuid.uuid4()), "kind": kind, "created_at": now(),
                  "source": source, "source_hash": source_hash(source), "project_id": project_id}
        payload = {"id": record["id"], "owner_id": self.owner_id, "project_id": project_id,
                   "kind": kind, "source": source, "source_hash": record["source_hash"],
                   "created_at": record["created_at"], "configuration": result.get("configuration", {}),
                   "result": record, "error": result.get("error")}
        self._request("POST", "qore_runs", body=payload)
        return record

    def run(self, ident):
        ident = self._id(ident)
        if not ident:
            return None
        rows = self._request("GET", "qore_runs", params={"id": f"eq.{ident}", "select": "result", "limit": "1"})
        return rows[0]["result"] if rows else None

    def runs(self):
        return [r["result"] for r in self._request("GET", "qore_runs", params={"select": "result", "order": "created_at.desc", "limit": "100"})]

    def add_experiment(self, record):
        record = {**record, "id": str(uuid.uuid4()), "created_at": now()}
        payload = {"id": record["id"], "owner_id": self.owner_id, "project_id": record.get("project_id"),
                   "simulation_id": (record.get("simulation") or {}).get("id"),
                   "optimization_id": (record.get("optimization") or {}).get("id"),
                   "name": record["name"], "source": record["source"], "source_hash": record["source_hash"],
                   "snapshot": record, "created_at": record["created_at"]}
        self._request("POST", "qore_experiments", body=payload)
        return record

    def experiments(self):
        return self._request("GET", "qore_experiments", params={"select": "id,project_id,name,created_at,source_hash", "order": "created_at.desc", "limit": "1000"})

    def experiment(self, ident):
        ident = self._id(ident)
        if not ident:
            return None
        rows = self._request("GET", "qore_experiments", params={"id": f"eq.{ident}", "select": "snapshot", "limit": "1"})
        return rows[0]["snapshot"] if rows else None

    @staticmethod
    def _workspace_result(value):
        """Return only contract fields, never provider/authentication metadata."""
        if not isinstance(value, dict):
            raise ValueError("Invalid workspace response")
        if "files" in value:
            return {"files": [CloudStore._workspace_result(row) for row in value["files"]],
                    "folders": [CloudStore._workspace_result(row) for row in value["folders"]],
                    "trash": [CloudStore._workspace_result(row) for row in value["trash"]],
                    "active_file_id": value["active_file_id"], "last_deleted_id": value["last_deleted_id"],
                    "retention_hours": 48, "server_time": value["server_time"]}
        return {key: value[key] for key in ("id", "path", "name", "type", "source", "kind", "version", "created_at", "updated_at", "deleted_at", "expires_at")}

    def _workspace_rpc(self, operation, payload=None):
        # Owner identity and timestamps are derived inside the database from the
        # verified user's JWT. They are deliberately absent from this body.
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=httpx.Timeout(15, connect=5), transport=self.transport, trust_env=False) as client:
                response = client.post(self.url + "rpc/qore_workspace", headers=headers,
                                       json={"operation": operation, "payload": payload or {}})
            response.raise_for_status()
            value = response.json()
            if isinstance(value, dict) and isinstance(value.get("error"), dict):
                code = value["error"].get("code")
                if code in WORKSPACE_ERRORS:
                    status, message = WORKSPACE_ERRORS[code]
                    raise JobError(code, message, status=status)
                raise ValueError("Invalid workspace error")
            return self._workspace_result(value)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise JobError("storage_unavailable", "Your private workspace could not be reached. Please retry.", status=503) from None

    def workspace_snapshot(self):
        return self._workspace_rpc("snapshot")

    def workspace_put(self, ident, entry_type, path, source, kind, expected_version=0):
        ident = self._id(ident)
        if not ident:
            raise JobError("workspace_not_found", "Workspace item not found.", status=404)
        return self._workspace_rpc("put", {"id": ident, "type": entry_type, "path": path,
                                          "source": source, "kind": kind, "expected_version": expected_version})

    def workspace_delete(self, ident, entry_type, expected_version):
        ident = self._id(ident)
        if not ident:
            raise JobError("workspace_not_found", "Workspace item not found.", status=404)
        return self._workspace_rpc("delete", {"id": ident, "type": entry_type, "expected_version": expected_version})

    def workspace_restore(self, ident, entry_type):
        ident = self._id(ident)
        if not ident:
            raise JobError("workspace_not_found", "Workspace item not found.", status=404)
        return self._workspace_rpc("restore", {"id": ident, "type": entry_type})

    def workspace_state(self, active_file_id):
        if active_file_id is not None:
            active_file_id = self._id(active_file_id)
            if not active_file_id:
                raise JobError("workspace_not_found", "Workspace item not found.", status=404)
        return self._workspace_rpc("state", {"active_file_id": active_file_id})

    def workspace_undo(self):
        return self._workspace_rpc("undo")
