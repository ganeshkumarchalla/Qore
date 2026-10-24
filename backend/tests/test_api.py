"""HTTP integration and persistent provenance tests with real SQLite and Aer."""

from hashlib import sha256

import pytest
from fastapi.testclient import TestClient


def assert_error(response):
    assert 400 <= response.status_code < 500, response.text
    error = response.json()["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]


def test_health_and_examples_are_usable(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["versions"] and health.json()["limits"]
    examples = client.get("/api/examples").json()
    assert examples
    for example in examples:
        assert {"id", "name", "description", "source"} <= set(example)
        assert client.post("/api/parse", json={"source": example["source"]}).status_code == 200


def test_project_create_edit_open_and_list(client, bell_source):
    created = client.post("/api/projects", json={"name": "Bell experiment", "source": bell_source})
    assert created.status_code in (200, 201), created.text
    project = created.json()
    assert project["id"] and project["created_at"] and project["updated_at"]
    assert project["source"] == bell_source
    edited_source = bell_source + "# Saved revision\n"
    renamed = client.put(f"/api/projects/{project['id']}", json={"name": "Renamed Bell", "source": edited_source})
    assert renamed.status_code == 200
    reopened = client.get(f"/api/projects/{project['id']}").json()
    assert reopened["name"] == "Renamed Bell"
    assert reopened["source"] == edited_source
    assert reopened["created_at"] == project["created_at"]
    assert project["id"] in [item["id"] for item in client.get("/api/projects").json()]


def test_full_workflow_records_provenance_and_reopens_immutable_evidence(client, bell_source):
    project = client.post("/api/projects", json={"name": "Bell", "source": bell_source}).json()
    parsed = client.post("/api/parse", json={"source": bell_source}).json()
    simulation_response = client.post("/api/simulate", json={"source": bell_source, "shots": 1024, "seed": 42, "project_id": project["id"]})
    assert simulation_response.status_code == 200, simulation_response.text
    simulation = simulation_response.json()
    optimization_response = client.post("/api/optimize", json={"source": bell_source, "level": 2, "seed": 42, "project_id": project["id"]})
    assert optimization_response.status_code == 200, optimization_response.text
    optimization = optimization_response.json()
    for run, kind in ((simulation, "simulation"), (optimization, "optimization")):
        assert run["id"] and run["created_at"] and run["kind"] == kind
        assert run["source"] == bell_source
        assert run["source_hash"] == parsed["source_hash"]
        assert run["project_id"] == project["id"]
        assert run["versions"]
    assert sum(simulation["counts"].values()) == 1024
    assert optimization["validation"]["status"] == "validated"
    saved_response = client.post("/api/experiments", json={"name": "Bell run 42", "project_id": project["id"], "source": bell_source, "simulation_id": simulation["id"], "optimization_id": optimization["id"]})
    assert saved_response.status_code in (200, 201), saved_response.text
    saved = saved_response.json()
    assert saved["ir_version"] == "1.0"
    assert saved["source_hash"] == sha256(bell_source.encode("utf-8")).hexdigest()
    assert saved["simulation"] == simulation
    assert saved["optimization"] == optimization
    assert saved["versions"]
    # A later project edit must never change the historical experiment.
    assert client.put(f"/api/projects/{project['id']}", json={"name": "Edited", "source": bell_source + "# later edit\n"}).status_code == 200
    reopened = client.get(f"/api/experiments/{saved['id']}")
    assert reopened.status_code == 200
    assert reopened.json() == saved
    listed = client.get("/api/experiments").json()
    summary = next(item for item in listed if item["id"] == saved["id"])
    assert summary["source_hash"] == saved["source_hash"]
    # Public API exposes immutable snapshots, not update/delete operations.
    assert client.put(f"/api/experiments/{saved['id']}", json={"name": "tamper"}).status_code == 405
    assert client.delete(f"/api/experiments/{saved['id']}").status_code == 405


def test_sqlite_records_survive_application_recreation(tmp_path, bell_source):
    from qore.main import create_app

    database = tmp_path / "restart.sqlite3"
    with TestClient(create_app(database)) as first:
        project = first.post("/api/projects", json={"name": "Persistent", "source": bell_source}).json()
        run = first.post("/api/simulate", json={"source": bell_source, "shots": 64, "seed": 11}).json()
        saved = first.post("/api/experiments", json={"name": "Persistent evidence", "source": bell_source, "simulation_id": run["id"]}).json()
    with TestClient(create_app(database)) as reopened:
        assert reopened.get(f"/api/projects/{project['id']}").json() == project
        assert reopened.get(f"/api/experiments/{saved['id']}").json() == saved


def test_experiment_rejects_run_with_different_exact_source(client, bell_source):
    run = client.post("/api/simulate", json={"source": bell_source, "shots": 64, "seed": 1}).json()
    response = client.post("/api/experiments", json={"name": "Mismatched", "source": bell_source + "# changed\n", "simulation_id": run["id"]})
    assert_error(response)
    assert not client.get("/api/experiments").json()


def test_experiment_rejects_wrong_run_kind_and_unknown_run(client, bell_source):
    run = client.post("/api/simulate", json={"source": bell_source, "shots": 64, "seed": 1}).json()
    assert_error(client.post("/api/experiments", json={"name": "Wrong kind", "source": bell_source, "optimization_id": run["id"]}))
    assert_error(client.post("/api/experiments", json={"name": "Missing", "source": bell_source, "simulation_id": "not-a-run"}))


@pytest.mark.parametrize("path,payload", [
    ("/api/parse", {"source": "import os"}),
    ("/api/parse", {"source": "#" + "x" * 32768}),
    ("/api/parse", {"source": 123}),
    ("/api/parse", {}),
    ("/api/simulate", {"source": "from qiskit import QuantumCircuit\nqc=QuantumCircuit(1,1)", "shots": 0}),
    ("/api/simulate", {"source": "from qiskit import QuantumCircuit\nqc=QuantumCircuit(1,1)", "shots": 100001}),
    ("/api/optimize", {"source": "from qiskit import QuantumCircuit\nqc=QuantumCircuit(1,1)", "level": 4}),
    ("/api/projects", {"name": "", "source": ""}),
    ("/api/projects", {"name": "x" * 500, "source": ""}),
])
def test_invalid_requests_use_consistent_error_envelope(client, path, payload):
    assert_error(client.post(path, json=payload))


def test_error_recovery_and_not_found(client, bell_source):
    assert_error(client.post("/api/simulate", json={"source": "raise Exception('failed')", "shots": 10, "seed": 1}))
    assert client.post("/api/parse", json={"source": bell_source}).status_code == 200
    assert_error(client.get("/api/projects/not-found"))
    assert_error(client.get("/api/experiments/not-found"))
    assert_error(client.post("/api/parse", content="{invalid json", headers={"Content-Type": "application/json"}))


def test_assistant_unavailable_is_honest_and_core_functionality_still_works(client, bell_source):
    response = client.post("/api/assistant", json={"question": "Explain this Bell circuit", "source": bell_source})
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["answer"]
    assert client.post("/api/parse", json={"source": bell_source}).status_code == 200


@pytest.mark.parametrize("extra", [
    {"api_key": "must-never-enter-the-browser-contract"},
    {"model": "client-selected-model"},
])
def test_assistant_rejects_client_credentials_and_provider_configuration(client, bell_source, extra):
    response = client.post(
        "/api/assistant",
        json={"question": "Explain the circuit", "source": bell_source, **extra},
    )
    assert response.status_code == 422
    assert_error(response)


@pytest.mark.parametrize("headers", [
    {"Origin": "https://untrusted.example"},
    {"Sec-Fetch-Site": "cross-site"},
    {"Origin": "http://localhost:8000.untrusted.example"},
    {"Origin": "null"},
])
def test_browser_cross_site_writes_are_rejected(client, bell_source, headers):
    response = client.post("/api/projects", headers=headers, json={"name": "Rejected", "source": bell_source})
    assert response.status_code == 403
    assert_error(response)
    assert client.get("/api/projects").json() == []


def test_loopback_origin_is_allowed_and_untrusted_host_is_rejected(client, bell_source):
    allowed = client.post("/api/projects", headers={"Origin": "http://localhost:5173"}, json={"name": "Local", "source": bell_source})
    assert allowed.status_code == 201
    assert client.get("/api/health", headers={"Host": "untrusted.example"}).status_code == 400


@pytest.mark.parametrize("chunked", [False, True])
def test_request_size_limit_applies_without_trusting_content_length(client, chunked):
    oversized = b"x" * 100000
    content = (oversized[i:i + 4096] for i in range(0, len(oversized), 4096)) if chunked else oversized
    headers = {"Content-Type": "application/json"}
    if not chunked:
        headers["Content-Length"] = "1"
    response = client.post("/api/parse", content=content, headers=headers)
    assert response.status_code == 413
    assert_error(response)
    assert client.get("/api/health").status_code == 200


def test_utf8_source_byte_cap_and_strict_execution_inputs(client, bell_source):
    assert_error(client.post("/api/parse", json={"source": "#" + "π" * 17000}))
    for field, value in (("shots", True), ("shots", "1024"), ("seed", -1), ("seed", 2147483648)):
        assert_error(client.post("/api/simulate", json={"source": bell_source, field: value}))
    assert_error(client.post("/api/parse", json={"source": bell_source, "shell": "cmd.exe"}))
    for payload in (
        {"noise_rate": "0.1"},
        {"readout_error": True},
        {"method": "automatic"},
    ):
        assert_error(client.post("/api/simulate", json={"source": bell_source, **payload}))


def test_failed_runs_are_preserved_and_cannot_be_attached_as_successful_evidence(client):
    source = "import os\nos.getcwd()"
    response = client.post("/api/simulate", json={"source": source, "shots": 64, "seed": 4})
    assert_error(response)
    run_id = response.json()["error"]["details"]["run_id"]
    failed = client.get(f"/api/runs/{run_id}").json()
    assert failed["source"] == source
    assert failed["configuration"] == {"shots": 64, "seed": 4}
    assert failed["error"]["code"]
    assert_error(client.post("/api/experiments", json={"name": "Cannot claim success", "source": source, "simulation_id": run_id}))
    assert client.get("/api/experiments").json() == []


def test_user_names_are_persisted_as_data_not_sql(client, bell_source):
    name = "Bell'); DROP TABLE projects; --"
    response = client.post("/api/projects", json={"name": name, "source": bell_source})
    assert response.status_code == 201
    assert client.get(f"/api/projects/{response.json()['id']}").json()["name"] == name
    assert len(client.get("/api/projects").json()) == 1
