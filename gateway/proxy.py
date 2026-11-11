"""Bounded API forwarding shared by the Render and AWS ingress gateways."""

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


REQUEST_HEADERS = {"accept", "content-type", "cookie", "origin", "sec-fetch-site"}
RESPONSE_HEADERS = {
    "content-type", "cache-control", "set-cookie", "x-content-type-options",
    "x-frame-options", "referrer-policy", "x-robots-tag",
}
MAX_REQUEST_BYTES = 96 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


async def forward_api(request: Request, backend_origin: str, *, gateway_token: str = "") -> Response:
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
    if gateway_token:
        headers["x-qore-gateway-token"] = gateway_token
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
