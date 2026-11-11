"""Render's static frontend and same-origin gateway for the AWS QORE API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware


REQUEST_HEADERS = {"accept", "content-type", "cookie", "origin", "sec-fetch-site"}
RESPONSE_HEADERS = {
    "content-type", "cache-control", "set-cookie", "x-content-type-options",
    "x-frame-options", "referrer-policy", "x-robots-tag",
}
MAX_REQUEST_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class GatewayHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secured(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                names = {key.lower() for key, _ in headers}
                for key, value in ((b"x-content-type-options", b"nosniff"),
                                   (b"x-frame-options", b"DENY"),
                                   (b"referrer-policy", b"no-referrer")):
                    if key not in names:
                        headers.append((key, value))
                if b"cache-control" not in names:
                    policy = b"public, max-age=31536000, immutable" if scope["path"].startswith("/assets/") else b"no-store"
                    headers.append((b"cache-control", policy))
            await send(message)

        await self.app(scope, receive, secured)


def _origin(value: str, *, https_only: bool) -> str:
    parsed = urlsplit(value)
    schemes = {"https"} if https_only else {"http", "https"}
    if (parsed.scheme not in schemes or not parsed.hostname or parsed.username
            or parsed.password or parsed.path not in {"", "/"} or parsed.query
            or parsed.fragment):
        raise ValueError("Configure a valid origin without a path or credentials")
    return value.rstrip("/")


def create_app(*, backend_origin: str, public_origin: str,
               static_dir: Path, transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    backend_origin = _origin(backend_origin, https_only=True)
    public_origin = _origin(public_origin, https_only=True)
    if not static_dir.joinpath("index.html").is_file():
        raise ValueError("Built frontend assets are missing")
    public_host = urlsplit(public_origin).netloc.lower()

    @asynccontextmanager
    async def lifespan(application: Starlette):
        async with httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(75.0, connect=5.0),
                                     follow_redirects=False, trust_env=False) as client:
            application.state.backend_client = client
            yield

    async def api(request: Request) -> Response:
        if request.headers.get("host", "").lower() != public_host:
            return JSONResponse({"error": {"code": "invalid_host", "message": "Invalid host."}}, status_code=400)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin", "")
            if origin and origin != public_origin:
                return JSONResponse({"error": {"code": "origin_denied", "message": "Cross-origin writes are not allowed."}}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": {"code": "origin_denied", "message": "Cross-site writes are not allowed."}}, status_code=403)
        if request.headers.get("content-length", "").isdigit() and int(request.headers["content-length"]) > MAX_REQUEST_BYTES:
            return JSONResponse({"error": {"code": "request_too_large", "message": "Request exceeds 96 KiB."}}, status_code=413)
        chunks, received = [], 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_REQUEST_BYTES:
                return JSONResponse({"error": {"code": "request_too_large", "message": "Request exceeds 96 KiB."}}, status_code=413)
            chunks.append(chunk)
        body = b"".join(chunks)
        headers = {key: value for key, value in request.headers.items() if key.lower() in REQUEST_HEADERS}
        headers["accept-encoding"] = "identity"
        target = backend_origin + request.url.path
        if request.url.query:
            target += "?" + request.url.query
        try:
            async with request.app.state.backend_client.stream(request.method, target,
                                                                headers=headers, content=body) as upstream:
                chunks, size = [], 0
                async for chunk in upstream.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        return JSONResponse({"error": {"code": "upstream_too_large", "message": "API response exceeded the gateway limit."}}, status_code=502)
                    chunks.append(chunk)
                response = Response(b"".join(chunks), status_code=upstream.status_code)
                for key, value in upstream.headers.multi_items():
                    if key.lower() in RESPONSE_HEADERS:
                        response.raw_headers.append((key.encode("latin1"), value.encode("latin1")))
                response.headers["x-robots-tag"] = "noindex, nofollow, noarchive"
                response.headers["cache-control"] = "no-store"
                return response
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError):
            return JSONResponse({"error": {"code": "backend_unavailable", "message": "The QORE backend is temporarily unavailable."}}, status_code=502)

    async def api_root(_request: Request) -> Response:
        return JSONResponse({"error": {"code": "not_found", "message": "API route not found."}}, status_code=404)

    async def gateway_health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "role": "frontend-gateway"}, headers={"cache-control": "no-store"})

    app = Starlette(routes=[
        Route("/healthz", gateway_health),
        Route("/api", api_root),
        Route("/api/{path:path}", api, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
        Mount("/", app=StaticFiles(directory=str(static_dir), html=True)),
    ], lifespan=lifespan)
    app.add_middleware(GatewayHeaders)
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[public_host.split(":", 1)[0], "localhost", "127.0.0.1"])
    return app


def create_from_env() -> Starlette:
    return create_app(
        backend_origin=os.environ.get("QORE_AWS_API_ORIGIN", ""),
        public_origin=os.environ.get("QORE_PUBLIC_URL", "https://qore-bmh1.onrender.com"),
        static_dir=Path(os.environ.get("QORE_FRONTEND_DIST", "/app/frontend/dist")),
    )
