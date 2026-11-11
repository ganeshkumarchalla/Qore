"""Gateway tests use a mocked AWS origin; they do not contact live services."""

import asyncio
from pathlib import Path

import httpx
import pytest

from gateway.app import create_app


PUBLIC = "https://qore-bmh1.onrender.com"
BACKEND = "https://backend.example.net"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<html>QORE</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('qore')", encoding="utf-8")
    return tmp_path


def run_request(static_dir: Path, handler, method="GET", path="/api/health", gateway_token="", **kwargs):
    app = create_app(backend_origin=BACKEND, public_origin=PUBLIC, static_dir=static_dir,
                     gateway_token=gateway_token, transport=httpx.MockTransport(handler))

    async def check():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC) as client:
                return await client.request(method, path, **kwargs)

    return asyncio.run(check())


def test_api_stays_on_public_origin_and_preserves_workspace_cookie(static_dir):
    seen = []

    def backend(request):
        seen.append(request)
        return httpx.Response(201, json={"ok": True}, headers={
            "set-cookie": "qore_workspace=123; Path=/; HttpOnly; Secure; SameSite=Lax",
            "x-robots-tag": "noindex", "cache-control": "no-store",
        })

    result = run_request(static_dir, backend, method="POST", path="/api/simulate?mode=fast",
                         headers={"Origin": PUBLIC, "Cookie": "qore_workspace=old", "Sec-Fetch-Site": "same-origin"},
                         json={"source": "H(q[0]);"})
    assert result.status_code == 201
    assert result.json() == {"ok": True}
    assert result.headers["set-cookie"].startswith("qore_workspace=123;")
    assert result.headers["content-type"] == "application/json"
    assert result.headers["x-robots-tag"] == "noindex, nofollow, noarchive"
    assert len(seen) == 1
    assert str(seen[0].url) == BACKEND + "/api/simulate?mode=fast"
    assert seen[0].headers["origin"] == PUBLIC
    assert seen[0].headers["cookie"] == "qore_workspace=old"
    assert seen[0].headers["host"] == "backend.example.net"


def test_cross_origin_write_rejected_before_backend(static_dir):
    called = []
    result = run_request(static_dir, lambda request: called.append(request), method="POST", path="/api/simulate",
                         headers={"Origin": "https://attacker.example"}, json={"source": "x"})
    assert result.status_code == 403
    assert called == []


def test_frontend_served_locally_without_backend(static_dir):
    result = run_request(static_dir, lambda _: pytest.fail("static request must not hit backend"), path="/")
    assert result.status_code == 200
    assert "QORE" in result.text
    assert result.headers["x-content-type-options"] == "nosniff"
    assert result.headers["cache-control"] == "no-store"


def test_static_assets_are_compressed_and_cacheable(static_dir):
    (static_dir / "assets" / "app.js").write_text("const value = 'qore';\n" * 2000, encoding="utf-8")
    result = run_request(static_dir, lambda _: pytest.fail("assets must not hit backend"), path="/assets/app.js",
                         headers={"Accept-Encoding": "gzip"})
    assert result.status_code == 200
    assert result.headers["content-encoding"] == "gzip"
    assert result.headers["cache-control"].endswith("immutable")


def test_missing_assets_are_not_cached(static_dir):
    result = run_request(static_dir, lambda _: pytest.fail("assets must not hit backend"), path="/assets/missing.js")
    assert result.status_code == 404
    assert result.headers["cache-control"] == "no-store"


def test_gateway_health_does_not_depend_on_aws(static_dir):
    result = run_request(static_dir, lambda _: pytest.fail("health must not hit backend"), path="/healthz")
    assert result.status_code == 200
    assert result.json()["role"] == "frontend-gateway"


def test_backend_failure_is_safe(static_dir):
    def backend(_request):
        raise httpx.ConnectError("private connection details")

    result = run_request(static_dir, backend)
    assert result.status_code == 502
    assert "private connection details" not in result.text


def test_gateway_secret_reaches_only_the_backend(static_dir):
    seen = []
    token = "test-only-gateway-token-with-enough-length"

    def backend(request):
        seen.append(request.headers.get("x-qore-gateway-token"))
        return httpx.Response(200, json={"ok": True})

    result = run_request(static_dir, backend, gateway_token=token)
    assert result.status_code == 200
    assert seen == [token]
    assert token not in result.text
    assert token not in str(result.headers)


def test_backend_origin_requires_https(static_dir):
    with pytest.raises(ValueError):
        create_app(backend_origin="http://backend.example.net", public_origin=PUBLIC, static_dir=static_dir)


def test_oversized_stream_is_rejected_before_backend(static_dir):
    called = []
    result = run_request(static_dir, lambda request: called.append(request), method="POST", path="/api/simulate",
                         content=b"x" * (96 * 1024 + 1))
    assert result.status_code == 413
    assert called == []


def test_real_backend_cookie_and_project_survive_gateway_round_trip(static_dir, tmp_path, monkeypatch):
    from qore.main import create_app as create_backend

    token = "test-only-gateway-token-with-enough-length"
    monkeypatch.setenv("QORE_GATEWAY_TOKEN", token)
    monkeypatch.setenv("QORE_ENV", "production")
    monkeypatch.setenv("QORE_PUBLIC_URL", PUBLIC)
    monkeypatch.setenv("QORE_ALLOWED_HOSTS", "backend.example.net")
    backend = create_backend(tmp_path / "workspace.sqlite3")
    gateway = create_app(backend_origin=BACKEND, public_origin=PUBLIC, static_dir=static_dir,
                         gateway_token=token, transport=httpx.ASGITransport(app=backend))

    async def check():
        async with backend.router.lifespan_context(backend):
            async with gateway.router.lifespan_context(gateway):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url=PUBLIC) as client:
                    source = "from qiskit import QuantumCircuit\nqc = QuantumCircuit(1)\nqc.h(0)\n"
                    saved = await client.post("/api/projects", headers={"Origin": PUBLIC},
                                              json={"name": "Live workspace", "source": source})
                    assert saved.status_code == 201
                    assert "qore_workspace" in client.cookies
                    assert client.cookies.get("qore_workspace")
                    listed = await client.get("/api/projects")
                    assert listed.status_code == 200
                    assert listed.json()[0]["name"] == "Live workspace"

    asyncio.run(check())
