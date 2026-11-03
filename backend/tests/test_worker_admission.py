"""Alternate HTTP routes must never bypass the normal execution admission."""
import asyncio


def test_no_unbounded_worker_endpoint(client, monkeypatch):
    from qore import quantum

    def forbidden(*args, **kwargs):
        raise AssertionError("Quantum execution must not occur without admission")

    monkeypatch.setattr(quantum, "parse_source", forbidden)
    assert not any(getattr(route, "path", None) == "/api/worker" for route in client.app.routes)
    response = client.post("/api/worker", json={"operation": "parse", "args": {"source": "ignored"}})
    assert response.status_code in (404, 405)


def test_normal_parse_still_requires_admission(client):
    class FullSlots:
        async def acquire(self):
            raise asyncio.TimeoutError()

        def release(self):
            raise AssertionError("No slot was acquired")

    client.app.state.job_slots = FullSlots()
    response = client.post("/api/parse", json={"source": "from qiskit import QuantumCircuit\nqc = QuantumCircuit(1)"})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "busy"


def test_obsolete_remote_worker_setting_cannot_override_local_engine(monkeypatch):
    from qore import runtime

    class OldWorker:
        def post(self, *args, **kwargs):
            return type("Response", (), {
                "status_code": 422,
                "json": lambda self: {"error": {"code": "SYNTAX_ERROR", "message": "old worker"}},
            })()

    monkeypatch.setenv("QORE_WORKER_HOST", "https://obsolete.example")
    monkeypatch.setattr(runtime, "_get_remote_client", lambda **kwargs: OldWorker(), raising=False)
    source = 'OPENQASM 2.0; include "qelib1.inc"; qreg q[1]; creg c[1]; h q[0]; measure q[0] -> c[0];'
    parsed = runtime.run_worker("parse", {"source": source}, timeout=15)
    assert parsed["language"] == "openqasm-2"
