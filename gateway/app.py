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

from gateway.proxy import forward_api



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
               static_dir: Path, gateway_token: str = "",
               transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
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
        return await forward_api(request, backend_origin, gateway_token=gateway_token)

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
    gateway_token = os.environ.get("QORE_GATEWAY_TOKEN", "")
    if len(gateway_token) < 32:
        raise ValueError("QORE_GATEWAY_TOKEN must contain at least 32 characters")
    return create_app(
        backend_origin=os.environ.get("QORE_AWS_API_ORIGIN", ""),
        public_origin=os.environ.get("QORE_PUBLIC_URL", "https://qore-bmh1.onrender.com"),
        static_dir=Path(os.environ.get("QORE_FRONTEND_DIST", "/app/frontend/dist")),
        gateway_token=gateway_token,
    )
