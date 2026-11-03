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
