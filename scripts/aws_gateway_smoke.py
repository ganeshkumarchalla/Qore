"""Verify the prepared Render gateway against the real AWS API, read-only.

The token file stays outside the repository. No workspace source or model
responses are printed. This does not change Render configuration.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

from gateway.app import create_app


async def check(backend_origin: str, public_origin: str, static_dir: Path, token: str) -> None:
    app = create_app(backend_origin=backend_origin, public_origin=public_origin,
                     static_dir=static_dir, gateway_token=token)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url=public_origin, timeout=45) as client:
            index = await client.get("/")
            assert index.status_code == 200 and "text/html" in index.headers["content-type"]
            health = await client.get("/api/health")
            health.raise_for_status()
            assert health.json()["status"] == "ok" and health.json()["ai_available"] is True
            capabilities = await client.get("/api/capabilities")
            capabilities.raise_for_status()
            assert {"qsharp", "openqasm-2"} <= {x["id"] for x in capabilities.json()["languages"]}
            first = await client.get("/api/workspace")
            second = await client.get("/api/workspace")
            first.raise_for_status()
            second.raise_for_status()
            assert client.cookies.get("qore_workspace")
            assert first.json()["files"] == second.json()["files"]
            denied = await client.post("/api/parse", headers={"Origin": "https://untrusted.invalid"},
                                       json={"source": ""})
            assert denied.status_code == 403
    print("PASS real AWS gateway: static UI, health, SDKs, workspace cookie, origin guard")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-origin", required=True)
    parser.add_argument("--public-origin", default="https://qore-bmh1.onrender.com")
    parser.add_argument("--static-dir", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--secrets-file", type=Path, required=True)
    args = parser.parse_args()
    values = dict(line.split("=", 1) for line in args.secrets_file.read_text(encoding="utf-8").splitlines()
                  if line and "=" in line)
    token = values.get("QORE_GATEWAY_TOKEN", "")
    assert len(token) >= 32
    asyncio.run(check(args.backend_origin, args.public_origin, args.static_dir, token))


if __name__ == "__main__":
    main()
