"""Durable editable workspace behavior, concurrency, isolation and 48-hour Trash."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from qore.auth import ACCESS_COOKIE, AuthSettings
from qore.cloud_store import CloudStore
from qore.runtime import JobError
from qore.store import Store
from qore import workspace


OWNER_A = "56ff9066-d9ab-4230-b45d-c2466421a101"
OWNER_B = "56ff9066-d9ab-4230-b45d-c2466421a102"


@pytest.fixture
def application(tmp_path, monkeypatch):
    for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "QORE_REQUIRE_AUTH", "QORE_ENV", "RENDER", "RENDER_EXTERNAL_URL", "QORE_STORAGE"):
        monkeypatch.delenv(name, raising=False)
    from qore.main import create_app
    return create_app(tmp_path / "workspace.sqlite3")


@pytest.fixture
def client(application):
    with TestClient(application) as value:
        yield value


def put(client, path="circuits/personal.py", source="", ident=None, version=0):
    return client.put("/api/workspace/files/" + (ident or str(uuid4())), json={"path": path, "source": source, "kind": "python", "expected_version": version})


def current(client):
    response = client.get("/api/workspace")
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_files_persist_after_refresh_and_application_restart(application, tmp_path):
    from qore.main import create_app
    with TestClient(application) as first:
        empty = current(first)
        assert empty["files"] == empty["folders"] == empty["trash"] == []
        assert empty["active_file_id"] is None and empty["retention_hours"] == 48
        ident = str(uuid4())
        created = put(first, ident=ident).json()
        assert created["id"] == ident and created["source"] == "" and created["version"] == 1
        assert created["name"] == "personal.py" and created["deleted_at"] is created["expires_at"] is None
        assert "owner_id" not in created
        assert first.patch("/api/workspace/state", json={"active_file_id": ident}).status_code == 200
        assert current(first)["files"] == [created]
    with TestClient(create_app(tmp_path / "workspace.sqlite3")) as restarted:
        result = current(restarted)
        assert result["files"] == [created] and result["active_file_id"] == ident


def test_idempotent_create_and_optimistic_save_do_not_overwrite_newer_edits(client):
    ident = str(uuid4())
    first = put(client, ident=ident, source="# first").json()
    assert put(client, ident=ident, source="# first").json() == first
    changed = put(client, ident=ident, source="# second", version=1).json()
    assert changed["version"] == 2 and changed["created_at"] == first["created_at"]
    assert put(client, ident=ident, source="# second", version=1).json() == changed
    stale = put(client, ident=ident, source="# stale tab", version=1)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "workspace_version_conflict"
    assert current(client)["files"] == [changed]
    assert put(client, ident=ident, source="# missing expected version").status_code == 409


@pytest.mark.parametrize("path", ["../a.py", "/a.py", "a//b.py", "a\\b.py", "a/./b.py", "a/../b.py", "a/:b.py", "a/\nfile.py", "a/" + "x" * 101, "trailing/"])
def test_paths_cannot_escape_or_break_the_virtual_workspace(client, path):
    assert put(client, path=path).status_code == 422
    assert current(client)["files"] == []


def test_utf8_size_limit_kind_and_unknown_fields_are_rejected(client):
    assert put(client, source="😀" * 8193).status_code == 422
    ident = str(uuid4())
    assert client.put("/api/workspace/files/" + ident, json={"path": "x.py", "source": "", "kind": "executable"}).status_code == 422
    assert client.put("/api/workspace/files/" + ident, json={"path": "x.py", "source": "", "kind": "python", "owner_id": OWNER_B}).status_code == 422
    assert current(client)["files"] == []


def test_active_path_uniqueness_and_file_as_parent_are_enforced(client):
    first = put(client, path="code.py").json()
    assert put(client, path="code.py").status_code == 409
    assert put(client, path="code.py/child.py").status_code == 409
    assert client.put("/api/workspace/folders/" + str(uuid4()), json={"path": "code.py"}).status_code == 409
    assert current(client)["files"] == [first]


def test_folder_rename_is_atomic_prefix_safe_and_preserves_stable_file_ids(client):
    folder_id = str(uuid4())
    assert client.put("/api/workspace/folders/" + folder_id, json={"path": "a/b"}).status_code == 200
    first = put(client, path="a/b/x.py", source="# one").json()
    nested = put(client, path="a/b/b/x.py", source="# two").json()
    outsider = put(client, path="a/bother/keep.py", source="# outside").json()
    folder = next(row for row in current(client)["folders"] if row["id"] == folder_id)
    renamed = client.put("/api/workspace/folders/" + folder_id, json={"path": "a", "expected_version": folder["version"]})
    assert renamed.status_code == 200, renamed.text
    result = {row["id"]: row for row in current(client)["files"]}
    assert result[first["id"]]["path"] == "a/x.py" and result[nested["id"]]["path"] == "a/b/x.py"
    assert result[outsider["id"]] == outsider
    assert result[first["id"]]["source"] == "# one" and result[first["id"]]["version"] == 2


def test_folder_conflicts_and_child_edit_races_preserve_every_file(client):
    folder_id = str(uuid4())
    folder = client.put("/api/workspace/folders/" + folder_id, json={"path": "source"}).json()
    child = put(client, path="source/a.py", source="# saved").json()
    stale_delete = client.request("DELETE", "/api/workspace/folders/" + folder_id, json={"expected_version": folder["version"]})
    assert stale_delete.status_code == 409
    put(client, path="destination/a.py", source="# occupied")
    before = current(client)
    fresh = next(row for row in before["folders"] if row["id"] == folder_id)
    conflict = client.put("/api/workspace/folders/" + folder_id, json={"path": "destination", "expected_version": fresh["version"]})
    assert conflict.status_code == 409
    assert current(client)["files"] == before["files"]
    assert current(client)["folders"] == before["folders"]
    into_itself = client.put("/api/workspace/folders/" + folder_id, json={"path": "source/nested", "expected_version": fresh["version"]})
    assert into_itself.status_code == 409
    assert next(row for row in current(client)["files"] if row["id"] == child["id"])["source"] == "# saved"


def test_delete_restore_undo_and_path_collision_never_lose_source(client, monkeypatch):
    moment = datetime(2030, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(workspace, "clock", lambda: moment)
    file = put(client, source="# important").json()
    client.patch("/api/workspace/state", json={"active_file_id": file["id"]})
    assert client.request("DELETE", "/api/workspace/files/" + file["id"], json={"expected_version": 999}).status_code == 409
    deleted = client.request("DELETE", "/api/workspace/files/" + file["id"], json={"expected_version": file["version"]}).json()
    assert deleted["files"] == [] and deleted["active_file_id"] is None
    assert deleted["trash"][0]["source"] == "# important"
    assert datetime.fromisoformat(deleted["trash"][0]["expires_at"]) - datetime.fromisoformat(deleted["trash"][0]["deleted_at"]) == timedelta(hours=48)
    moment += timedelta(hours=1)
    repeated = client.request("DELETE", "/api/workspace/files/" + file["id"], json={"expected_version": file["version"]}).json()
    assert repeated["trash"] == deleted["trash"]
    assert put(client, ident=file["id"], source="# no resurrection").status_code == 409
    occupied = put(client, source="# replacement").json()
    assert client.post("/api/workspace/files/" + file["id"] + "/restore").status_code == 409
    moved = put(client, path="circuits/replacement.py", source=occupied["source"], ident=occupied["id"], version=occupied["version"])
    assert moved.status_code == 200
    restored = client.post("/api/workspace/undo").json()
    assert any(row["id"] == file["id"] and row["source"] == "# important" for row in restored["files"])
    assert restored["trash"] == [] and restored["last_deleted_id"] is None


def test_folder_restore_uses_its_deletion_batch_and_leaves_older_trash_alone(client):
    folder_id = str(uuid4())
    client.put("/api/workspace/folders/" + folder_id, json={"path": "circuits"})
    old = put(client, path="circuits/old.py", source="# old").json()
    client.request("DELETE", "/api/workspace/files/" + old["id"], json={"expected_version": old["version"]})
    fresh = put(client, path="circuits/fresh.py", source="# fresh").json()
    folder = current(client)["folders"][0]
    deleted = client.request("DELETE", "/api/workspace/folders/" + folder_id, json={"expected_version": folder["version"]}).json()
    assert len(deleted["trash"]) == 3 and deleted["files"] == []
    restored = client.post("/api/workspace/folders/" + folder_id + "/restore").json()
    assert [row["id"] for row in restored["files"]] == [fresh["id"]]
    assert [row["id"] for row in restored["trash"]] == [old["id"]]


def test_exact_48_hour_cutoff_permanent_purge_and_stale_uuid_protection(tmp_path, monkeypatch):
    moment = datetime(2030, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(workspace, "clock", lambda: moment)
    store = Store(tmp_path / "cutoff.sqlite3").for_owner(OWNER_A)
    ident = str(uuid4())
    file = store.workspace_put(ident, "file", "keep.py", "saved source", "python", 0)
    store.workspace_delete(ident, "file", file["version"])
    moment += timedelta(hours=48, microseconds=-1)
    assert len(store.workspace_snapshot()["trash"]) == 1
    moment += timedelta(microseconds=1)
    assert store.workspace_snapshot()["trash"] == []
    with pytest.raises(JobError) as expired:
        store.workspace_restore(ident, "file")
    assert expired.value.status == 404
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM workspace_entries WHERE id=?", (ident,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM workspace_tombstones WHERE id=?", (ident,)).fetchone()[0] == 1
    with pytest.raises(JobError) as stale:
        store.workspace_put(ident, "file", "keep.py", "stale offline create", "python", 0)
    assert stale.value.code == "workspace_deleted" and stale.value.status == 409


def test_active_files_do_not_expire_and_global_cleanup_leaves_ledger_untouched(tmp_path, monkeypatch):
    moment = datetime(2030, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(workspace, "clock", lambda: moment)
    base = Store(tmp_path / "retention.sqlite3")
    alice, bob = base.for_owner(OWNER_A), base.for_owner(OWNER_B)
    permanent = alice.workspace_put(str(uuid4()), "file", "permanent.py", "lasting work", "python", 0)
    removed = bob.workspace_put(str(uuid4()), "file", "trash.py", "temporary", "python", 0)
    bob.workspace_delete(removed["id"], "file", removed["version"])
    project = alice.save_project("Ledger project", "historical source")
    run = alice.add_run("simulation", "historical source", project["id"], {"counts": {"0": 32}})
    moment += timedelta(days=3650)
    assert base.workspace_purge_all() == 1
    assert alice.workspace_snapshot()["files"] == [permanent]
    assert bob.workspace_snapshot()["trash"] == []
    assert alice.project(project["id"]) == project and alice.run(run["id"]) == run


def test_owners_cannot_read_modify_restore_or_set_other_accounts_files(tmp_path):
    base = Store(tmp_path / "owners.sqlite3")
    alice, bob = base.for_owner(OWNER_A), base.for_owner(OWNER_B)
    private = alice.workspace_put(str(uuid4()), "file", "private.py", "private work", "python", 0)
    assert bob.workspace_snapshot()["files"] == []
    actions = [lambda: bob.workspace_put(private["id"], "file", "private.py", "overwrite", "python", 1),
               lambda: bob.workspace_delete(private["id"], "file", 1), lambda: bob.workspace_restore(private["id"], "file"),
               lambda: bob.workspace_state(private["id"])]
    for action in actions:
        with pytest.raises(JobError) as denied:
            action()
        assert denied.value.status == 404
    assert alice.workspace_snapshot()["files"] == [private]


def test_workspace_storage_limits_fail_without_discarding_existing_work(tmp_path, monkeypatch):
    store = Store(tmp_path / "limits.sqlite3")
    monkeypatch.setattr(workspace, "MAX_ENTRIES", 1)
    file = store.workspace_put(str(uuid4()), "file", "first.py", "123456", "python", 0)
    with pytest.raises(JobError, match="item limit"):
        store.workspace_put(str(uuid4()), "file", "second.py", "", "python", 0)
    monkeypatch.setattr(workspace, "MAX_WORKSPACE_BYTES", 6)
    with pytest.raises(JobError, match="storage limit"):
        store.workspace_put(file["id"], "file", "first.py", "1234567", "python", 1)
    assert store.workspace_snapshot()["files"] == [file]


def test_cloud_workspace_rpc_uses_verified_token_never_sends_owner_or_leaks_metadata(tmp_path):
    base = Store(tmp_path / "rpc.sqlite3")
    calls = []
    token_a, token_b = "fixture-owner-a-token", "fixture-owner-b-token"

    def provider(request):
        calls.append(request)
        assert request.url.path == "/rest/v1/rpc/qore_workspace" and not request.url.query
        payload = json.loads(request.content)
        assert set(payload) == {"operation", "payload"}
        assert "owner_id" not in payload["payload"]
        assert token_a not in request.content.decode() and token_b not in request.content.decode()
        owner = OWNER_A if request.headers["authorization"] == "Bearer " + token_a else OWNER_B
        store = base.for_owner(owner)
        data, operation = payload["payload"], payload["operation"]
        try:
            if operation == "snapshot":
                result = store.workspace_snapshot()
            elif operation == "put":
                result = store.workspace_put(data["id"], data["type"], data["path"], data["source"], data["kind"], data["expected_version"])
            elif operation == "delete":
                result = store.workspace_delete(data["id"], data["type"], data["expected_version"])
            elif operation == "restore":
                result = store.workspace_restore(data["id"], data["type"])
            elif operation == "state":
                result = store.workspace_state(data["active_file_id"])
            else:
                result = store.workspace_undo()
            return httpx.Response(200, json={**result, "owner_id": owner, "access_token": token_a})
        except JobError as error:
            return httpx.Response(200, json={"error": {"code": error.code, "message": token_a}})

    transport = httpx.MockTransport(provider)
    alice = CloudStore("https://workspace.example.test", "publishable-fixture", OWNER_A, token_a, transport)
    bob = CloudStore("https://workspace.example.test", "publishable-fixture", OWNER_B, token_b, transport)
    file = alice.workspace_put(str(uuid4()), "file", "cloud.py", "saved", "python", 0)
    assert "owner_id" not in file and "access_token" not in file
    assert bob.workspace_snapshot()["files"] == []
    with pytest.raises(JobError) as denied:
        bob.workspace_put(file["id"], "file", "cloud.py", "overwrite", "python", 1)
    assert denied.value.status == 404 and token_a not in str(denied.value)
    assert alice.workspace_state(file["id"])["active_file_id"] == file["id"]
    assert alice.workspace_delete(file["id"], "file", 1)["files"] == []
    assert alice.workspace_restore(file["id"], "file")["files"][0]["source"] == "saved"
    alice.workspace_undo()
    assert len(calls) == 7
    assert token_a not in json.dumps(file)


@pytest.mark.parametrize("failure", ["http", "json", "shape", "unknown_error"])
def test_cloud_workspace_failures_are_sanitized(failure):
    marker = "sensitive-provider-diagnostic"
    def provider(_request):
        if failure == "http":
            return httpx.Response(500, text=marker)
        if failure == "json":
            return httpx.Response(200, text=marker)
        return httpx.Response(200, json={"error": {"code": marker}} if failure == "unknown_error" else {"invalid": marker})
    store = CloudStore("https://workspace.example.test", "publishable-fixture", OWNER_A, "fixture-owner-token", httpx.MockTransport(provider))
    with pytest.raises(JobError) as unavailable:
        store.workspace_snapshot()
    assert unavailable.value.status == 503 and marker not in str(unavailable.value)


def test_api_workspace_identity_is_verified_and_owner_scoped(application):
    def provider(request):
        owner = OWNER_B if request.headers.get("authorization") == "Bearer fixture-account-b" else OWNER_A
        return httpx.Response(200, json={"id": owner, "email": "member@example.test"})
    application.state.auth.settings = AuthSettings("https://identity.example.test", "publishable-fixture", "http://127.0.0.1:8000", True)
    application.state.auth.transport = httpx.MockTransport(provider)
    with TestClient(application) as client:
        assert client.get("/api/workspace").status_code == 401
        client.cookies.set(ACCESS_COOKIE, "fixture-account-a")
        file = put(client, source="# account A").json()
        client.cookies.clear()
        client.cookies.set(ACCESS_COOKIE, "fixture-account-b")
        assert current(client)["files"] == []
        assert put(client, ident=file["id"], source="# account B", version=1).status_code == 404
        assert client.request("DELETE", "/api/workspace/files/" + file["id"], json={"expected_version": 1}).status_code == 404
        assert client.post("/api/workspace/files/" + file["id"] + "/restore").status_code == 404
