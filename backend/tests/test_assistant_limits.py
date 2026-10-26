"""Shared AI credentials need bounded per-account requests and provider work."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from qore.main import create_app


SOURCE = "from qiskit import QuantumCircuit\nqc=QuantumCircuit(1)\nqc.h(0)"
BODY = {"source": SOURCE, "question": "Explain this circuit"}
REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def local_ai(monkeypatch, tmp_path):
    for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY",
                 "QORE_ENV", "QORE_REQUIRE_AUTH", "RENDER", "RENDER_EXTERNAL_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-provider-value")
    monkeypatch.setenv("QORE_STORAGE", "sqlite")
    return create_app(tmp_path / "assistant.sqlite3")


def provider_client(monkeypatch, call):
    class Client:
        def __init__(self, **_options):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            pass
        async def post(self, _url, **_options):
            return await call()
    monkeypatch.setattr("qore.main.httpx.AsyncClient", Client)


def response(status=200):
    return httpx.Response(status, request=httpx.Request("POST", "https://provider.example.test"),
        json={"candidates": [{"content": {"parts": [{"text": "Fixture explanation"}]}}]})


def test_ai_budget_prevents_additional_provider_calls_without_blocking_editor(local_ai, monkeypatch):
    calls = []
    async def call():
        calls.append(True)
        return response()
    provider_client(monkeypatch, call)
    with TestClient(local_ai) as client:
        for _ in range(10):
            assert client.post("/api/assistant", json=BODY).json()["available"] is True
        blocked = client.post("/api/assistant", json=BODY)
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "rate_limited"
        assert len(calls) == 10
        assert client.post("/api/parse", json={"source": SOURCE}).status_code == 200


def test_provider_failure_does_not_leak_concurrency_slots(local_ai, monkeypatch):
    calls = []
    async def call():
        calls.append(True)
        return response(500 if len(calls) < 4 else 200)
    provider_client(monkeypatch, call)
    with TestClient(local_ai) as client:
        for _ in range(3):
            assert client.post("/api/assistant", json=BODY).json()["available"] is False
        assert client.post("/api/assistant", json=BODY).json()["available"] is True


def test_unavailable_configured_model_falls_back_to_current_stable_model(local_ai, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "retired-model")
    requested = []

    class Client:
        def __init__(self, **_options):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            pass
        async def post(self, url, **_options):
            requested.append(url)
            return response(404 if "retired-model" in url else 200)

    monkeypatch.setattr("qore.main.httpx.AsyncClient", Client)
    with TestClient(local_ai) as client:
        result = client.post("/api/assistant", json=BODY)
    assert result.status_code == 200
    assert result.json()["available"] is True
    assert result.json()["model"] == "gemini-3.6-flash"
    assert len(requested) == 2
    assert requested[1].endswith("/gemini-3.6-flash:generateContent")


def test_parallel_ai_requests_never_exceed_two_provider_calls(local_ai, monkeypatch):
    active = 0
    peak = 0
    async def call():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(.04)
            return response()
        finally:
            active -= 1
    provider_client(monkeypatch, call)
    async def requests():
        async with local_ai.router.lifespan_context(local_ai):
            async with REAL_ASYNC_CLIENT(transport=httpx.ASGITransport(app=local_ai), base_url="http://testserver") as client:
                results = await asyncio.gather(*(client.post("/api/assistant", json=BODY) for _ in range(5)))
                assert all(item.status_code == 200 and item.json()["available"] for item in results)
    asyncio.run(requests())
    assert peak == 2
    assert active == 0
