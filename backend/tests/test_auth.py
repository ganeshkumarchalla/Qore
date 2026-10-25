"""Authentication boundary tests use an isolated mocked identity provider."""
import asyncio
import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from qore.auth import (
    ACCESS_COOKIE, REFRESH_COOKIE, STATE_COOKIE, VERIFIER_COOKIE,
    AuthSettings, current_identity, register_auth,
)

USER_ID = "c7f73659-f339-4cb5-9b31-3fb384279718"
USER = {"id": USER_ID, "email": "member@example.test", "user_metadata": {"full_name": "Qore Member"}}
SETTINGS = AuthSettings("https://identity.example.test", "publishable-test-value", "https://qore.example.test", True, enable_google=True)
TOKENS = {"access_token": "test-access-verified", "refresh_token": "test-refresh-verified", "expires_in": 3600}


def auth_app(handler, settings=SETTINGS):
    application = FastAPI()
    service = register_auth(application, settings=settings, transport=httpx.MockTransport(handler))

    @application.get("/api/private")
    async def private():
        identity = current_identity.get()
        return {"owner_id": identity["owner_id"] if identity else None}

    @application.get("/api/health")
    async def health():
        return {"status": "ok"}

    return application, service


def normal_provider(request):
    if request.url.path.endswith("/settings"):
        return httpx.Response(200, json={"external": {"google": True, "email": True}})
    if request.url.path.endswith("/user"):
        return httpx.Response(200, json=USER)
    if request.url.path.endswith("/token"):
        return httpx.Response(200, json=TOKENS)
    if request.url.path.endswith("/logout"):
        return httpx.Response(204)
    return httpx.Response(404, json={})


def test_production_fails_closed_without_credentials_but_health_stays_public():
    app, _service = auth_app(normal_provider, AuthSettings(require_auth=True))
    with TestClient(app, base_url="https://qore.example.test") as client:
        config = client.get("/api/auth/config")
        assert config.json() == {"configured": False, "required": True, "google_enabled": False, "email_enabled": False}
        assert config.headers["cache-control"] == "no-store"
        assert client.get("/api/private").status_code == 503
        assert client.get("/api/health").status_code == 200


def test_unauthenticated_personal_data_is_rejected_without_provider_lookup():
    def never_called(_request):
        pytest.fail("An empty session must not reach the identity provider")
    app, _service = auth_app(never_called)
    with TestClient(app, base_url="https://qore.example.test") as client:
        assert client.get("/api/private").status_code == 401


def test_signin_uses_server_only_session_cookies_and_verified_identity():
    app, _service = auth_app(normal_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        response = client.post("/api/auth/signin", json={"email": USER["email"], "password": "example-password-only"})
        assert response.status_code == 200
        assert response.json()["user"]["id"] == USER_ID
        assert not {"access_token", "refresh_token", "token"}.intersection(response.json()["user"])
        for header in response.headers.get_list("set-cookie"):
            assert "HttpOnly" in header and "Secure" in header and "SameSite=lax" in header
        assert client.get("/api/private").json() == {"owner_id": USER_ID}
        assert current_identity.get() is None
        assert client.get("/api/auth/session").json()["user"]["name"] == "Qore Member"


def test_provider_errors_are_redacted_and_password_is_never_reflected():
    supplied_password = secrets.token_urlsafe(24)
    def invalid_provider(_request):
        return httpx.Response(400, json={"error_description": supplied_password, "access_token": "should-not-appear"})
    app, _service = auth_app(invalid_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        response = client.post("/api/auth/signin", json={"email": USER["email"], "password": supplied_password})
        assert response.status_code == 401
        assert supplied_password not in response.text
        assert "should-not-appear" not in response.text


def test_signup_confirmation_does_not_fabricate_a_session():
    def pending_provider(request):
        assert request.url.path.endswith("/signup")
        return httpx.Response(200, json={"id": USER_ID, "identities": []})
    app, _service = auth_app(pending_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        response = client.post("/api/auth/signup", json={"email": USER["email"], "name": "Qore Member", "password": "a-long-fixture-password"})
        assert response.status_code == 200
        assert response.json()["user"] is None
        assert not response.headers.get_list("set-cookie")


def test_invalid_signup_password_is_not_echoed_in_validation_error():
    app, _service = auth_app(normal_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        response = client.post("/api/auth/signup", json={"email": USER["email"], "name": "Qore Member", "password": "tiny"})
        assert response.status_code == 422
        assert "tiny" not in response.text


def test_google_redirect_has_pkce_and_request_bound_state():
    app, _service = auth_app(normal_provider)
    with TestClient(app, base_url="https://qore.example.test", follow_redirects=False) as client:
        response = client.get("/api/auth/google")
        assert response.status_code == 303
        target = urlsplit(response.headers["location"])
        assert target.scheme == "https" and target.netloc == "identity.example.test"
        query = parse_qs(target.query)
        assert query["provider"] == ["google"] and query["code_challenge_method"] == ["s256"]
        expected = base64.urlsafe_b64encode(hashlib.sha256(client.cookies[VERIFIER_COOKIE].encode()).digest()).decode().rstrip("=")
        assert query["code_challenge"] == [expected]
        callback = urlsplit(query["redirect_to"][0])
        assert callback.netloc == "qore.example.test" and callback.path == "/api/auth/callback"
        assert parse_qs(callback.query)["state"] == [client.cookies[STATE_COOKIE]]
        for header in response.headers.get_list("set-cookie"):
            assert "HttpOnly" in header and "Secure" in header and "Max-Age=600" in header


def test_callback_requires_matching_state_and_verifier_without_provider_call():
    called = []
    def provider(request):
        called.append(request.url.path)
        return normal_provider(request)
    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test", follow_redirects=False) as client:
        client.get("/api/auth/google")
        called.clear()
        response = client.get("/api/auth/callback?code=one-use-code&state=attacker-state")
        assert response.headers["location"] == "/?auth_error=signin_failed"
        assert called == []
        assert STATE_COOKIE not in client.cookies and VERIFIER_COOKIE not in client.cookies


def test_unicode_callback_state_is_rejected_without_an_internal_error():
    app, _service = auth_app(normal_provider)
    with TestClient(app, base_url="https://qore.example.test", follow_redirects=False) as client:
        client.get("/api/auth/google")
        response = client.get("/api/auth/callback", params={"code": "one-use-code", "state": "é" * 43})
        assert response.status_code == 303
        assert response.headers["location"] == "/?auth_error=signin_failed"


def test_callback_query_is_removed_from_the_server_logging_scope():
    seen = []
    app, _service = auth_app(normal_provider)

    class ObserveLogScope:
        def __init__(self, wrapped):
            self.wrapped = wrapped
        async def __call__(self, scope, receive, send):
            await self.wrapped(scope, receive, send)
            seen.append(scope.get("query_string"))

    with TestClient(ObserveLogScope(app), base_url="https://qore.example.test", follow_redirects=False) as client:
        client.get("/api/auth/callback?code=one-use-code&state=invalid")
        assert seen[-1] == b""


def test_pkce_callback_exchanges_only_with_the_bound_server_verifier():
    calls = []
    def provider(request):
        if request.url.path.endswith("/token"):
            calls.append((request.url.params["grant_type"], json.loads(request.content)))
        return normal_provider(request)
    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test", follow_redirects=False) as client:
        client.get("/api/auth/google")
        state, verifier = client.cookies[STATE_COOKIE], client.cookies[VERIFIER_COOKIE]
        response = client.get("/api/auth/callback", params={"code": "one-use-code", "state": state})
        assert response.status_code == 303 and response.headers["location"] == "/"
        assert calls == [("pkce", {"auth_code": "one-use-code", "code_verifier": verifier})]
        assert client.get("/api/private").json()["owner_id"] == USER_ID
        assert STATE_COOKIE not in client.cookies and VERIFIER_COOKIE not in client.cookies


def test_query_stripped_callback_still_requires_browser_bound_oauth_cookies():
    app, _service = auth_app(normal_provider)
    with TestClient(app, base_url="https://qore.example.test", follow_redirects=False) as client:
        client.get("/api/auth/google")
        # The provider may omit the redirect query. PKCE and the initiation
        # cookie still bind this response to this same browser's login attempt.
        response = client.get("/api/auth/callback", params={"code": "one-use-code"})
        assert response.headers["location"] == "/"
        assert client.get("/api/private").json()["owner_id"] == USER_ID


def test_callback_rejects_missing_initiation_cookie_and_hides_provider_error():
    calls = []
    def provider(request):
        calls.append(request.url.path)
        return normal_provider(request)
    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test", follow_redirects=False) as client:
        client.cookies.set(VERIFIER_COOKIE, "v" * 64)
        response = client.get("/api/auth/callback", params={"code": "one-use-code"})
        assert response.headers["location"] == "/?auth_error=signin_failed"
        assert calls == []
        response = client.get("/api/auth/callback", params={"error": "provider-internal-detail"})
        assert response.headers["location"] == "/?auth_error=signin_failed"


def test_expired_access_token_is_refreshed_and_cookies_rotated():
    def provider(request):
        if request.url.path.endswith("/user") and request.headers.get("authorization") == "Bearer expired-fixture-token":
            return httpx.Response(401, json={})
        return normal_provider(request)
    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        client.cookies.set(ACCESS_COOKIE, "expired-fixture-token")
        client.cookies.set(REFRESH_COOKIE, "refresh-fixture-token")
        response = client.get("/api/private")
        assert response.status_code == 200 and response.json()["owner_id"] == USER_ID
        assert len(response.headers.get_list("set-cookie")) == 2


def test_invalid_refresh_session_is_cleared_and_rejected():
    def invalid_provider(_request):
        return httpx.Response(401, json={})
    app, _service = auth_app(invalid_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        client.cookies.set(ACCESS_COOKIE, "invalid-fixture-token")
        client.cookies.set(REFRESH_COOKIE, "invalid-refresh-token")
        response = client.get("/api/private")
        assert response.status_code == 401
        assert all("Max-Age=0" in h for h in response.headers.get_list("set-cookie"))


def test_concurrent_expired_requests_share_one_refresh_rotation():
    calls = []
    async def provider(request):
        if request.url.path.endswith("/user") and request.headers.get("authorization") == "Bearer expired-fixture-token":
            return httpx.Response(401, json={})
        if request.url.path.endswith("/token"):
            calls.append("refresh")
            await asyncio.sleep(0)
        return normal_provider(request)
    _app, service = auth_app(provider)
    async def requests():
        cookies = {ACCESS_COOKIE: "expired-fixture-token", REFRESH_COOKIE: "refresh-fixture-token"}
        return await asyncio.gather(*(service.resolve(cookies) for _ in range(4)))
    resolved = asyncio.run(requests())
    assert calls == ["refresh"]
    assert all(item.user["id"] == USER_ID for item in resolved)


def test_identity_provider_outage_fails_closed_without_leaking_details():
    def offline_provider(request):
        raise httpx.ConnectError("internal transport configuration must not appear", request=request)
    app, _service = auth_app(offline_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        client.cookies.set(ACCESS_COOKIE, "fixture-access-token")
        response = client.get("/api/private")
        assert response.status_code == 503
        assert "transport configuration" not in response.text


def test_google_disabled_is_reported_honestly_and_not_redirected():
    def disabled_provider(_request):
        return httpx.Response(200, json={"external": {"google": False, "email": True}})
    app, _service = auth_app(disabled_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        assert client.get("/api/auth/config").json()["google_enabled"] is False
        assert client.get("/api/auth/google").status_code == 503


def test_signout_clears_sessions_even_when_provider_is_unavailable():
    def offline_provider(request):
        raise httpx.ConnectError("offline", request=request)
    app, _service = auth_app(offline_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        client.cookies.set(ACCESS_COOKIE, "fixture-access-token")
        response = client.post("/api/auth/signout")
        assert response.status_code == 200 and response.json() == {"user": None}
        assert len(response.headers.get_list("set-cookie")) == 4


def test_auth_attempts_are_bounded():
    def invalid_provider(_request):
        return httpx.Response(400, json={})
    app, _service = auth_app(invalid_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        body = {"email": USER["email"], "password": "fixture-password"}
        for _ in range(12):
            assert client.post("/api/auth/signin", json=body).status_code == 401
        assert client.post("/api/auth/signin", json=body).status_code == 429


def test_privileged_provider_keys_are_not_accepted_as_public_configuration():
    assert not AuthSettings("https://identity.example.test", "sb_secret_forbidden-key", "https://qore.example.test", True).configured


def test_deployed_environment_defaults_to_required_auth(monkeypatch):
    for key in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY", "QORE_REQUIRE_AUTH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert AuthSettings.from_env().require_auth is True

