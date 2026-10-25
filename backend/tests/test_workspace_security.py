"""Private workspace boundaries use real SQLite and isolated provider transports."""

import json
import sqlite3
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from qore.auth import ACCESS_COOKIE, AuthSettings, current_identity
from qore.cloud_store import CloudStore
from qore.runtime import JobError
from qore.store import Store, source_hash


OWNER_A = "d7c426ef-cc32-4b80-a5c7-1b1d8fe52011"
OWNER_B = "d7c426ef-cc32-4b80-a5c7-1b1d8fe52012"
ACCESS_A = "fixture-access-owner-a"
ACCESS_B = "fixture-access-owner-b"
SOURCE = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(1, 1)\nqc.measure(0, 0)\n"


def test_legacy_sqlite_migration_preserves_local_records_and_is_idempotent(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    run = {"id": "old-run", "source": SOURCE, "kind": "simulation"}
    experiment = {"id": "old-experiment", "source": SOURCE, "name": "Legacy evidence"}
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,source TEXT NOT NULL,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE runs(id TEXT PRIMARY KEY,project_id TEXT,kind TEXT NOT NULL,
                created_at TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE experiments(id TEXT PRIMARY KEY,project_id TEXT,name TEXT NOT NULL,
                created_at TEXT NOT NULL,source_hash TEXT NOT NULL,payload TEXT NOT NULL);
        """)
        db.execute("INSERT INTO projects VALUES (?,?,?,?,?)", ("old-project", "Legacy", SOURCE, "before", "before"))
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?)", ("old-run", "old-project", "simulation", "before", json.dumps(run)))
        db.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?)", ("old-experiment", "old-project", "Legacy evidence", "before", source_hash(SOURCE), json.dumps(experiment)))
    for _ in range(2):
        store = Store(path)
        assert store.project("old-project")["source"] == SOURCE
        assert store.run("old-run") == run
        assert store.experiment("old-experiment") == experiment
        account = store.for_owner(OWNER_A)
        assert account.projects() == account.runs() == account.experiments() == []
        assert account.project("old-project") is None
        assert account.run("old-run") is None
        assert account.experiment("old-experiment") is None
    with sqlite3.connect(path) as db:
        for table in ("projects", "runs", "experiments"):
            assert db.execute(f"SELECT owner_id FROM {table}").fetchone() == ("local",)


def test_sqlite_owner_filters_prevent_reads_overwrites_and_cross_owner_links(tmp_path):
    store = Store(tmp_path / "private.sqlite3")
    alice, bob = store.for_owner(OWNER_A), store.for_owner(OWNER_B)
    project = alice.save_project("Private circuit", SOURCE)
    run = alice.add_run("simulation", SOURCE, project["id"], {"counts": {"0": 16}})
    evidence = alice.add_experiment({"project_id": project["id"], "name": "Private evidence", "source": SOURCE, "source_hash": source_hash(SOURCE), "simulation": run})
    assert bob.projects() == bob.runs() == bob.experiments() == []
    assert bob.project(project["id"]) is None
    assert bob.run(run["id"]) is None
    assert bob.experiment(evidence["id"]) is None
    assert bob.save_project("Overwrite attempt", "changed", project["id"]) is None
    with pytest.raises(ValueError, match="Project not found"):
        bob.add_run("simulation", SOURCE, project["id"], {})
    with pytest.raises(ValueError, match="Project not found"):
        bob.add_experiment({"project_id": project["id"]})
    assert alice.project(project["id"]) == project
    assert alice.run(run["id"]) == run
    assert alice.experiment(evidence["id"]) == evidence
    assert not {"owner_id", "access_token", "refresh_token"}.intersection(project)
    with pytest.raises(ValueError, match="verified workspace owner"):
        store.for_owner(None)


def test_cloud_store_applies_owner_filter_to_every_query_and_uses_user_token_only():
    requests = []
    project_id = str(uuid4())

    def handler(request):
        requests.append(request)
        assert request.url.params["owner_id"] == f"eq.{OWNER_A}"
        assert request.headers["authorization"] == f"Bearer {ACCESS_A}"
        assert request.headers["apikey"] == "publishable-fixture"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["owner_id"] == OWNER_A
            assert ACCESS_A not in request.content.decode()
            return httpx.Response(201, json=[body])
        if request.method == "PATCH":
            return httpx.Response(200, json=[{"id": project_id, "owner_id": OWNER_A, **json.loads(request.content)}])
        return httpx.Response(200, json=[])

    store = CloudStore("https://workspace.example.test", "publishable-fixture", OWNER_A, ACCESS_A, httpx.MockTransport(handler))
    project = store.save_project("Circuit", SOURCE)
    assert "owner_id" not in project and ACCESS_A not in json.dumps(project)
    assert "owner_id" not in store.save_project("Renamed", SOURCE, project_id)
    store.projects()
    store.project(project_id)
    run = store.add_run("simulation", SOURCE, None, {"counts": {"0": 16}})
    store.runs()
    store.run(run["id"])
    experiment = store.add_experiment({"project_id": None, "name": "Evidence", "source": SOURCE, "source_hash": source_hash(SOURCE), "simulation": run})
    store.experiments()
    store.experiment(experiment["id"])
    assert len(requests) == 10
    assert ACCESS_A not in json.dumps([project, run, experiment])
    count = len(requests)
    for method in (store.project, store.run, store.experiment):
        assert method("invalid-id&owner_id=eq.other") is None
    assert store.save_project("Invalid", SOURCE, "invalid-id") is None
    assert len(requests) == count


def test_cloud_other_owner_cannot_read_or_patch_known_project_id():
    project_id = str(uuid4())
    private = {"id": project_id, "owner_id": OWNER_A, "name": "Private", "source": SOURCE}
    before = deepcopy(private)

    def handler(request):
        assert request.url.params["id"] == f"eq.{project_id}"
        permitted = request.url.params["owner_id"] == f"eq.{private['owner_id']}"
        if permitted and request.method == "PATCH":
            private.update(json.loads(request.content))
        return httpx.Response(200, json=[private] if permitted else [])

    bob = CloudStore("https://workspace.example.test", "publishable-fixture", OWNER_B, ACCESS_B, httpx.MockTransport(handler))
    assert bob.project(project_id) is None
    assert bob.save_project("Overwrite", "changed", project_id) is None
    assert private == before


@pytest.mark.parametrize("failure", ["forbidden", "invalid_json", "wrong_shape", "network"])
def test_cloud_errors_are_sanitized_and_do_not_reflect_provider_tokens(failure):
    marker = "fixture-provider-sensitive-detail"

    def handler(request):
        if failure == "network":
            raise httpx.ConnectError(marker + ACCESS_A, request=request)
        if failure == "forbidden":
            return httpx.Response(403, json={"error": marker, "access_token": ACCESS_A})
        if failure == "invalid_json":
            return httpx.Response(200, text=marker + ACCESS_A)
        return httpx.Response(200, json={"access_token": ACCESS_A})

    store = CloudStore("https://workspace.example.test", "publishable-fixture", OWNER_A, ACCESS_A, httpx.MockTransport(handler))
    with pytest.raises(JobError) as raised:
        store.projects()
    assert raised.value.status == 503
    assert raised.value.code == "storage_unavailable"
    assert marker not in str(raised.value) and ACCESS_A not in str(raised.value)
    assert raised.value.details is None


def test_full_api_verified_sessions_cannot_access_another_account_records(tmp_path, monkeypatch):
    for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "QORE_REQUIRE_AUTH", "QORE_ENV", "RENDER", "RENDER_EXTERNAL_URL", "QORE_STORAGE"):
        monkeypatch.delenv(name, raising=False)
    from qore.main import create_app

    def provider(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": ACCESS_A, "refresh_token": "fixture-refresh-owner-a", "expires_in": 3600})
        if request.url.path.endswith("/user"):
            owner = OWNER_B if request.headers.get("authorization") == f"Bearer {ACCESS_B}" else OWNER_A
            return httpx.Response(200, json={"id": owner, "email": "member@example.test", "user_metadata": {"full_name": "Test member"}, "access_token": "must-not-be-public"})
        return httpx.Response(404, json={})

    application = create_app(tmp_path / "api-private.sqlite3")
    application.state.auth.settings = AuthSettings("https://identity.example.test", "publishable-fixture", "http://127.0.0.1:8000", True)
    application.state.auth.transport = httpx.MockTransport(provider)
    with TestClient(application) as client:
        assert client.get("/api/projects").status_code == 401
        signed_in = client.post("/api/auth/signin", json={"email": "member@example.test", "password": "fixture-password-only"})
        assert signed_in.status_code == 200
        assert ACCESS_A not in signed_in.text and "must-not-be-public" not in signed_in.text
        assert not {"access_token", "refresh_token", "token"}.intersection(signed_in.json()["user"])
        assert all("HttpOnly" in header for header in signed_in.headers.get_list("set-cookie"))
        project = client.post("/api/projects", json={"name": "Owner A", "source": SOURCE}).json()
        scoped = application.state.store.for_owner(OWNER_A)
        run = scoped.add_run("simulation", SOURCE, project["id"], {"counts": {"0": 16}})
        snapshot = scoped.add_experiment({"project_id": project["id"], "name": "Evidence A", "source": SOURCE, "source_hash": source_hash(SOURCE)})
        client.cookies.clear()
        client.cookies.set(ACCESS_COOKIE, ACCESS_B)
        assert client.get("/api/projects").json() == []
        assert client.get("/api/runs").json() == []
        assert client.get("/api/experiments").json() == []
        for path in (f"/api/projects/{project['id']}", f"/api/runs/{run['id']}", f"/api/experiments/{snapshot['id']}"):
            assert client.get(path).status_code == 404
        assert client.put(f"/api/projects/{project['id']}", json={"name": "Overwrite", "source": SOURCE}).status_code == 404
        assert client.post("/api/simulate", json={"source": SOURCE, "project_id": project["id"]}).status_code == 404
        assert client.post("/api/experiments", json={"name": "Cross-account reference", "source": SOURCE, "simulation_id": run["id"]}).status_code == 404
        client.cookies.clear()
        client.cookies.set(ACCESS_COOKIE, ACCESS_A)
        assert client.get(f"/api/projects/{project['id']}").json() == project
        assert client.get(f"/api/runs/{run['id']}").json() == run
        assert client.get(f"/api/experiments/{snapshot['id']}").json() == snapshot
        assert current_identity.get() is None
