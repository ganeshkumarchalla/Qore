"""No-account runtime boundary and anonymous workspace isolation."""

from fastapi.testclient import TestClient

from qore.main import create_app


def test_auth_routes_are_not_exposed(tmp_path, monkeypatch):
    monkeypatch.setenv("QORE_STORAGE", "supabase")
    monkeypatch.setenv("QORE_REQUIRE_AUTH", "true")
    application = create_app(tmp_path / "no-auth.sqlite3")
    with TestClient(application) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert not any(path.startswith("/api/auth/") for path in paths)
        health = client.get("/api/health").json()
        assert health["auth_configured"] is False
        assert health["auth_required"] is False
        assert health["storage"] == "sqlite"


def test_anonymous_workspace_cookie_is_opaque_and_hardened(tmp_path):
    application = create_app(tmp_path / "anonymous.sqlite3")
    with TestClient(application) as client:
        response = client.get("/api/health")
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("qore_workspace=")
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie
        assert "access" not in cookie.lower()
        assert "refresh" not in cookie.lower()
        assert response.json().get("user") is None


def test_separate_browsers_receive_isolated_records(tmp_path):
    application = create_app(tmp_path / "isolated.sqlite3")
    source = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(1)\nqc.h(0)\n"
    with TestClient(application) as first, TestClient(application) as second:
        created = first.post("/api/projects", json={"name": "First", "source": source})
        assert created.status_code == 201
        assert len(first.get("/api/projects").json()) == 1
        assert second.get("/api/projects").json() == []
