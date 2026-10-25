"""Authentication boundary tests use an isolated mocked identity provider."""
import asyncio
import json
import secrets

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from qore.auth import (
    ACCESS_COOKIE, REFRESH_COOKIE,
    AuthSettings, current_identity, register_auth,
)

USER_ID = "c7f73659-f339-4cb5-9b31-3fb384279718"
USER = {"id": USER_ID, "email": "member@example.test", "user_metadata": {"full_name": "Qore Member"}}
SETTINGS = AuthSettings("https://identity.example.test", "publishable-test-value", "https://qore.example.test", True)
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
        assert config.json() == {"configured": False, "required": True, "email_enabled": False}
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


def test_signup_enforces_twelve_character_boundary_without_exposing_password():
    calls = []

    def provider(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"id": USER_ID})

    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        body = {"email": USER["email"], "name": "Qore Member", "password": "a" * 11}
        rejected = client.post("/api/auth/signup", json=body)
        assert rejected.status_code == 422
        assert body["password"] not in rejected.text
        assert calls == []
        accepted = client.post("/api/auth/signup", json={**body, "password": "a" * 12})
        assert accepted.status_code == 200
        assert calls == ["/auth/v1/signup"]


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


def test_deployed_environment_defaults_to_open_access(monkeypatch):
    for key in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY", "QORE_REQUIRE_AUTH"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert AuthSettings.from_env().require_auth is False


def test_email_only_config_and_retired_provider_has_no_route():
    app, _service = auth_app(normal_provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        assert client.get("/api/auth/config").json() == {"configured": True, "required": True, "email_enabled": True}
        assert "/api/auth/google" not in client.get("/openapi.json").json()["paths"]


def test_confirmation_resend_uses_server_redirect_and_generic_message():
    sent = []
    def provider(request):
        assert request.url.path.endswith("/resend")
        sent.append((dict(request.url.params), json.loads(request.content)))
        return httpx.Response(200, json={})
    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        result = client.post("/api/auth/resend", json={"email": USER["email"]})
        assert result.status_code == 200
        assert result.json()["message"].startswith("If this address has a pending account")
        assert sent == [({"redirect_to": "https://qore.example.test/?email_confirmation=opened"}, {"email": USER["email"], "type": "signup"})]
        assert client.post("/api/auth/resend", json={"email": USER["email"], "redirect_to": "https://attacker.example"}).status_code == 422


def test_unverified_email_receives_actionable_safe_error():
    def provider(_request):
        return httpx.Response(400, json={"error_code": "email_not_confirmed", "msg": "provider private detail"})
    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        result = client.post("/api/auth/signin", json={"email": USER["email"], "password": "fixture-password"})
        assert result.status_code == 401
        assert result.json()["error"]["code"] == "email_confirmation_required"
        assert "provider private detail" not in result.text



def test_recovery_otp_flow():
    def provider(request):
        if request.url.path.endswith("/recover"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/verify"):
            data = json.loads(request.content)
            if data.get("token") == "123456":
                return httpx.Response(200, json={"access_token": "verified-token", "user": USER})
            return httpx.Response(400, json={"error": "invalid_grant"})
        if request.url.path.endswith("/user") and request.method == "PUT":
            return httpx.Response(200, json=USER)
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json=TOKENS)
        if request.url.path.endswith("/user") and request.method == "GET":
            return httpx.Response(200, json=USER)
        return httpx.Response(404, json={})

    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        # 1. Request recovery OTP
        send_res = client.post("/api/auth/otp/send-recovery", json={"email": USER["email"]})
        assert send_res.status_code == 200
        assert "OTP" in send_res.json()["message"]

        # 2. Invalid OTP fails
        bad_res = client.post("/api/auth/otp/verify-reset", json={
            "email": USER["email"],
            "otp": "999999",
            "password": "brand-new-quantum-password-123"
        })
        assert bad_res.status_code == 400
        assert bad_res.json()["error"]["code"] == "invalid_otp"

        # 3. Valid OTP resets password and logs in
        good_res = client.post("/api/auth/otp/verify-reset", json={
            "email": USER["email"],
            "otp": "123456",
            "password": "brand-new-quantum-password-123"
        })
        assert good_res.status_code == 200
        assert good_res.json()["user"]["email"] == USER["email"]
        assert any("qore_access" in cookie for cookie in good_res.headers.get_list("set-cookie"))


def test_change_password_flow():
    def provider(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json=TOKENS)
        if request.url.path.endswith("/user") and request.method == "GET":
            return httpx.Response(200, json=USER)
        if request.url.path.endswith("/user") and request.method == "PUT":
            return httpx.Response(200, json=USER)
        return httpx.Response(404, json={})

    app, _service = auth_app(provider)
    with TestClient(app, base_url="https://qore.example.test") as client:
        # Unauthenticated cannot change password
        assert client.post("/api/auth/change-password", json={
            "current_password": "current-fixture-password",
            "new_password": "new-fixture-password-123"
        }).status_code == 401

        # Authenticate first
        client.post("/api/auth/signin", json={"email": USER["email"], "password": "fixture-password"})

        # Authenticated can change password
        res = client.post("/api/auth/change-password", json={
            "current_password": "fixture-password",
            "new_password": "new-fixture-password-123"
        })
        assert res.status_code == 200
        assert "Password changed successfully" in res.json()["message"]
