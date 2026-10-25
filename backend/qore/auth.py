"""Supabase authentication with server-only tokens and verified request identity.

Browser JavaScript receives a public profile, never access or refresh tokens.
The provider owns email credentials; QORE owns the HTTP-only cookie
boundary and verifies each authenticated identity with the provider's user API.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import time
from collections import OrderedDict, deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from http.cookies import CookieError, SimpleCookie
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator


current_identity: ContextVar[dict[str, Any] | None] = ContextVar("qore_identity", default=None)
ACCESS_COOKIE = "qore_access"
REFRESH_COOKIE = "qore_refresh"
STATE_COOKIE = "qore_oauth_state"
VERIFIER_COOKIE = "qore_pkce"
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]{8,8192}$")
PUBLIC_PATHS = {
    "/api/health", "/api/examples", "/api/auth/config", "/api/auth/session",
    "/api/auth/signin", "/api/auth/signup", "/api/auth/signout", "/api/auth/resend",
    "/api/auth/otp/send-recovery", "/api/auth/otp/verify-reset",
    "/api/quantum/onboarding-question",
}


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 401):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def send_smtp_email(to_email: str, subject: str, otp_code: str) -> bool:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS")
    smtp_from = os.environ.get("SMTP_FROM") or smtp_user or "no-reply@qore-quantum.com"
    if not (smtp_host and smtp_user and smtp_pass):
        return False
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"QORE Quantum Studio <{smtp_from}>"
        msg["To"] = to_email

        text_content = f"Your QORE verification OTP is: {otp_code}\n\nUse this code to reset your password in QORE Quantum Studio.\n"
        html_content = f"""
        <div style="background-color: #030712; color: #f8fafc; font-family: sans-serif; padding: 32px 20px; max-width: 540px; margin: 0 auto; border-radius: 12px; border: 1px solid rgba(56, 189, 248, 0.3);">
            <h2 style="color: #38bdf8; margin: 0 0 16px;">QORE QUANTUM STUDIO</h2>
            <p style="color: #cbd5e1; font-size: 14px; margin: 0 0 16px;">Your 6-digit password verification code (OTP) is:</p>
            <div style="font-size: 32px; font-weight: 800; letter-spacing: 6px; color: #00f0ff; background: rgba(0, 240, 255, 0.1); border: 1px solid rgba(0, 240, 255, 0.4); padding: 12px 24px; border-radius: 8px; display: inline-block; margin-bottom: 16px;">
                {otp_code}
            </div>
            <p style="color: #94a3b8; font-size: 12px; margin: 0;">This code expires in 15 minutes. If you did not request this code, no action is needed.</p>
        </div>
        """
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10.0) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception:
        return False


def _origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"} or (parsed.scheme != "https" and not local)):
            return ""
        # Reading port also validates malformed port syntax without exposing it.
        _ = parsed.port
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    except ValueError:
        return ""


def _privileged_key(value: str) -> bool:
    if value.startswith("sb_secret_"):
        return True
    try:
        payload = value.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return data.get("role") == "service_role"
    except (IndexError, ValueError, TypeError, AttributeError):
        return False


@dataclass(frozen=True)
class AuthSettings:
    supabase_url: str = ""
    publishable_key: str = field(default="", repr=False)
    public_url: str = "http://127.0.0.1:8000"
    require_auth: bool = False
    service_role_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "AuthSettings":
        url = _origin(os.environ.get("SUPABASE_URL", ""))
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
        service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        public = _origin(os.environ.get("QORE_PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000")
        production = bool(os.environ.get("RENDER")) or os.environ.get("QORE_ENV", "").lower() == "production"
        configured = bool(url and key and public and not _privileged_key(key))
        # Auth requirement removed: QORE Studio is open to all visitors without login.
        required = os.environ.get("QORE_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}
        return cls(url, key, public, required, service_key)

    @property
    def configured(self) -> bool:
        return bool(_origin(self.supabase_url) and self.publishable_key and _origin(self.public_url)
                    and not _privileged_key(self.publishable_key))

    @property
    def secure(self) -> bool:
        return self.public_url.startswith("https://")


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class SignInInput(EmailInput):
    password: str = Field(min_length=1, max_length=512, repr=False)


class SignUpInput(SignInInput):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128, repr=False)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter your name")
        return value


class RecoveryOtpSendInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class ResetPasswordOtpInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    otp: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=12, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("otp")
    @classmethod
    def valid_otp(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter the verification OTP code")
        return value


class ChangePasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str | None = Field(default=None, max_length=512, repr=False)
    new_password: str = Field(min_length=12, max_length=128, repr=False)


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    try:
        ident = str(UUID(str(user["id"])))
    except (KeyError, ValueError, TypeError):
        raise AuthError("invalid_session", "Please sign in again.") from None
    metadata = user.get("user_metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    email = str(user.get("email") or "")[:254]
    name = str(metadata.get("full_name") or metadata.get("name") or email.partition("@")[0] or "QORE member")[:80]
    name = " ".join(name.split())
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "Q"
    return {"id": ident, "email": email, "name": name, "avatarInitials": initials,
            "role": "Member", "tier": "Personal workspace"}


@dataclass
class ResolvedSession:
    user: dict[str, Any] | None = None
    access_token: str | None = field(default=None, repr=False)
    tokens: dict[str, Any] | None = field(default=None, repr=False)
    invalid: bool = False


class AuthService:
    def __init__(self, settings: AuthSettings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings, self.transport = settings, transport
        self._providers: tuple[float, dict[str, bool]] | None = None
        self._attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._refreshes: OrderedDict[str, tuple[float, asyncio.Task]] = OrderedDict()

    def ensure_configured(self) -> None:
        if not self.settings.configured:
            raise AuthError("auth_not_configured", "Sign-in is not configured for this deployment yet.", 503)

    def rate_limit(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self._attempts.setdefault(key, deque())
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= 12:
            raise AuthError("auth_rate_limited", "Too many sign-in attempts. Try again shortly.", 429)
        bucket.append(now)
        self._attempts.move_to_end(key)
        while len(self._attempts) > 4096:
            self._attempts.popitem(last=False)

    async def upstream(self, method: str, path: str, *, token: str | None = None,
                       payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        self.ensure_configured()
        headers = {"apikey": self.settings.publishable_key, "Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=5), transport=self.transport,
                                         trust_env=False, follow_redirects=False) as client:
                response = await client.request(method, self.settings.supabase_url + "/auth/v1" + path,
                                                headers=headers, json=payload)
            if len(response.content) > 1_048_576:
                raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
            data = response.json() if response.content else {}
            if not isinstance(data, dict):
                raise ValueError("Invalid provider response")
            return response.status_code, data
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503) from None

    async def providers(self) -> dict[str, bool]:
        if not self.settings.configured:
            return {"email_enabled": False}
        now = time.monotonic()
        if self._providers and now - self._providers[0] < 30:
            return self._providers[1]
        status, data = await self.upstream("GET", "/settings")
        if status != 200:
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
        external = data.get("external") or {}
        if not isinstance(external, dict):
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
        values = {"email_enabled": external.get("email", True) is True}
        self._providers = now, values
        return values

    async def verified_user(self, token: str) -> dict[str, Any]:
        if not TOKEN_PATTERN.fullmatch(token):
            raise AuthError("invalid_session", "Please sign in again.")
        status, user = await self.upstream("GET", "/user", token=token)
        if status >= 500:
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
        if status != 200:
            raise AuthError("invalid_session", "Please sign in again.")
        return public_user(user)

    async def token_exchange(self, grant: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        status, data = await self.upstream("POST", "/token?" + urlencode({"grant_type": grant}), payload=payload)
        if status == 429:
            raise AuthError("auth_rate_limited", "Too many sign-in attempts. Try again shortly.", 429)
        if status >= 500:
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
        if data.get("error_code") == "email_not_confirmed" or "email not confirmed" in str(data).lower():
            if self.settings.service_role_key and grant == "password" and payload.get("email"):
                try:
                    admin_headers = {
                        "apikey": self.settings.service_role_key,
                        "Authorization": f"Bearer {self.settings.service_role_key}",
                        "Content-Type": "application/json"
                    }
                    async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                        u_res = await client.get(
                            f"{self.settings.supabase_url}/auth/v1/admin/users",
                            headers=admin_headers,
                            params={"per_page": 100}
                        )
                        if u_res.status_code == 200:
                            target_user = next((u for u in u_res.json().get("users", []) if u.get("email", "").lower() == payload["email"].lower()), None)
                            if target_user:
                                uid = target_user["id"]
                                await client.put(
                                    f"{self.settings.supabase_url}/auth/v1/admin/users/{uid}",
                                    headers=admin_headers,
                                    json={"email_confirm": True}
                                )
                                retry_status, retry_data = await self.upstream("POST", "/token?" + urlencode({"grant_type": grant}), payload=payload)
                                if retry_status == 200 and isinstance(retry_data.get("access_token"), str):
                                    return retry_data, await self.verified_user(retry_data["access_token"])
                except Exception:
                    pass
            raise AuthError("email_confirmation_required", "Confirm your email before signing in. You can resend the confirmation email.")
        if status != 200 or not isinstance(data.get("access_token"), str) or not isinstance(data.get("refresh_token"), str):
            err_desc = str(data.get("error_description") or data.get("msg") or "").lower()
            if "invalid" in err_desc or "credential" in err_desc or status == 400:
                raise AuthError("invalid_credentials", "Invalid email or password. Use 'Forgot Password / Reset with OTP' below if you need to recover access.")
            raise AuthError("signin_failed", "Sign-in could not be completed. Check your details and try again.")
        if not TOKEN_PATTERN.fullmatch(data["refresh_token"]):
            raise AuthError("invalid_session", "Please sign in again.")
        return data, await self.verified_user(data["access_token"])

    async def resolve(self, cookies: dict[str, str]) -> ResolvedSession:
        if not self.settings.configured:
            return ResolvedSession()
        access, refresh = cookies.get(ACCESS_COOKIE, ""), cookies.get(REFRESH_COOKIE, "")
        if access:
            try:
                return ResolvedSession(await self.verified_user(access), access)
            except AuthError as error:
                if error.status != 401:
                    raise
        if refresh and TOKEN_PATTERN.fullmatch(refresh):
            try:
                # A page can issue several requests together just as the access
                # cookie expires. Reuse one rotation briefly so responses do not
                # race and overwrite a newly issued refresh cookie with stale data.
                digest = hashlib.sha256(refresh.encode()).hexdigest()
                now = time.monotonic()
                cached = self._refreshes.get(digest)
                if cached and now - cached[0] < 3:
                    task = cached[1]
                else:
                    task = asyncio.create_task(self.token_exchange("refresh_token", {"refresh_token": refresh}))
                    self._refreshes[digest] = now, task
                    self._refreshes.move_to_end(digest)
                    while len(self._refreshes) > 256:
                        self._refreshes.popitem(last=False)
                tokens, user = await asyncio.shield(task)
                return ResolvedSession(user, tokens["access_token"], tokens)
            except AuthError as error:
                if error.status != 401:
                    raise
        return ResolvedSession(invalid=bool(access or refresh))

    def set_session(self, response: Response, tokens: dict[str, Any]) -> None:
        try:
            expires = min(3600, max(30, int(tokens.get("expires_in", 3600))))
        except (TypeError, ValueError):
            expires = 3600
        for name, value, age in [(ACCESS_COOKIE, tokens["access_token"], expires),
                                  (REFRESH_COOKIE, tokens["refresh_token"], 7 * 86400)]:
            response.set_cookie(name, value, max_age=age, path="/", httponly=True,
                                secure=self.settings.secure, samesite="lax")

    def clear_session(self, response: Response) -> None:
        for name in (ACCESS_COOKIE, REFRESH_COOKIE):
            response.delete_cookie(name, path="/", secure=self.settings.secure, httponly=True, samesite="lax")

    def clear_legacy_cookies(self, response: Response) -> None:
        for name in (STATE_COOKIE, VERIFIER_COOKIE):
            response.delete_cookie(name, path="/api/auth", secure=self.settings.secure, httponly=True, samesite="lax")


def auth_error_response(error: AuthError) -> JSONResponse:
    return JSONResponse({"error": {"code": error.code, "message": error.message}}, error.status,
                        headers={"Cache-Control": "no-store"})


class SessionMiddleware:
    def __init__(self, app, service: AuthService):
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        scope.setdefault("state", {})
        scope["state"].update(user=None, owner_id=None, access_token=None)
        resolved = ResolvedSession()
        path = scope.get("path", "")
        token = current_identity.set(None)
        try:
            if path.startswith("/api/") and path not in PUBLIC_PATHS:
                if self.service.settings.require_auth and not self.service.settings.configured:
                    return await auth_error_response(AuthError("auth_not_configured", "Sign-in is not configured for this deployment yet.", 503))(scope, receive, send)
                raw = dict(scope.get("headers", [])).get(b"cookie", b"").decode("latin1")
                try:
                    parsed = SimpleCookie(raw)
                    cookies = {name: morsel.value for name, morsel in parsed.items()}
                except CookieError:
                    cookies = {}
                try:
                    resolved = await self.service.resolve(cookies)
                except AuthError as error:
                    return await auth_error_response(error)(scope, receive, send)
                if not resolved.user and self.service.settings.require_auth:
                    response = auth_error_response(AuthError("authentication_required", "Authentication is optional."))
                    if resolved.invalid:
                        self.service.clear_session(response)
                    return await response(scope, receive, send)
                if resolved.user:
                    identity = {"owner_id": resolved.user["id"], "user": resolved.user,
                                "access_token": resolved.access_token}
                    current_identity.set(identity)
                    scope["state"].update(identity)
                else:
                    identity = {"owner_id": "local", "user": None, "access_token": None}
                    current_identity.set(identity)
                    scope["state"].update(identity)
            async def session_send(message):
                if message["type"] == "http.response.start" and (resolved.tokens or resolved.invalid):
                    response = Response()
                    if resolved.tokens:
                        self.service.set_session(response, resolved.tokens)
                    elif resolved.invalid:
                        self.service.clear_session(response)
                    message.setdefault("headers", []).extend((k, v) for k, v in response.raw_headers if k == b"set-cookie")
                await send(message)
            await self.app(scope, receive, session_send)
        finally:
            current_identity.reset(token)


def register_auth(application: FastAPI, *, settings: AuthSettings | None = None,
                  transport: httpx.AsyncBaseTransport | None = None) -> AuthService:
    service = AuthService(settings or AuthSettings.from_env(), transport)
    application.state.auth = service
    application.add_middleware(SessionMiddleware, service=service)
    router = APIRouter(prefix="/api/auth")

    @application.exception_handler(AuthError)
    async def auth_error(_request, error):
        return auth_error_response(error)

    @application.exception_handler(RequestValidationError)
    async def safe_validation(_request, error):
        return JSONResponse({"error": {"code": "invalid_request", "message": "Please check the request fields.",
                                      "details": [{"location": list(item["loc"]), "message": item["msg"]} for item in error.errors()]}}, 422,
                            headers={"Cache-Control": "no-store"})

    @router.get("/config")
    async def config():
        result = {"configured": service.settings.configured, "required": service.settings.require_auth,
                  "email_enabled": False}
        try:
            result.update(await service.providers())
        except AuthError:
            result["message"] = "The sign-in service is temporarily unavailable."
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @router.get("/session")
    async def session(request: Request):
        resolved = await service.resolve(request.cookies)
        response = JSONResponse({"user": resolved.user, "configured": service.settings.configured,
                                 "required": service.settings.require_auth}, headers={"Cache-Control": "no-store"})
        if resolved.tokens:
            service.set_session(response, resolved.tokens)
        elif resolved.invalid:
            service.clear_session(response)
        return response


    @router.post("/signin")
    async def signin(payload: SignInInput, request: Request):
        service.ensure_configured()
        service.rate_limit(request)
        tokens, user = await service.token_exchange("password", {"email": payload.email, "password": payload.password})
        response = JSONResponse({"user": user}, headers={"Cache-Control": "no-store"})
        service.set_session(response, tokens)
        return response

    @router.post("/signup")
    async def signup(payload: SignUpInput, request: Request):
        service.ensure_configured()
        service.rate_limit(request)

        if service.settings.service_role_key:
            headers = {
                "apikey": service.settings.service_role_key,
                "Authorization": f"Bearer {service.settings.service_role_key}",
                "Content-Type": "application/json"
            }
            try:
                async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                    res = await client.post(
                        f"{service.settings.supabase_url}/auth/v1/admin/users",
                        headers=headers,
                        json={
                            "email": payload.email,
                            "password": payload.password,
                            "email_confirm": True,
                            "user_metadata": {"full_name": payload.name}
                        }
                    )
                    if res.status_code == 422:
                        raise AuthError("signup_failed", "An account with this email address already exists. Sign in instead.", 400)
                    if res.status_code not in {200, 201}:
                        raise AuthError("signup_failed", "Account creation could not be completed. Check your details and try again.", 400)
            except httpx.HTTPError:
                raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)

            # Auto-login newly registered user
            tokens, user = await service.token_exchange("password", {"email": payload.email, "password": payload.password})
            response = JSONResponse({"user": user, "message": "Account created successfully."}, headers={"Cache-Control": "no-store"})
            service.set_session(response, tokens)
            return response

        redirect = service.settings.public_url + "/?email_confirmation=opened"
        status, data = await service.upstream("POST", "/signup?" + urlencode({"redirect_to": redirect}), payload={"email": payload.email,
                                           "password": payload.password, "data": {"full_name": payload.name}})
        if status == 429:
            raise AuthError("auth_rate_limited", "Too many sign-in attempts. Try again shortly.", 429)
        if status not in {200, 201}:
            raise AuthError("signup_failed", "Account creation could not be completed. Check your details and try again.", 400)
        response = JSONResponse({"user": None, "message": "Check your email to confirm your account."},
                                headers={"Cache-Control": "no-store"})
        if data.get("access_token") and data.get("refresh_token"):
            user = await service.verified_user(data["access_token"])
            if not TOKEN_PATTERN.fullmatch(str(data["refresh_token"])):
                raise AuthError("invalid_session", "Please sign in again.")
            response = JSONResponse({"user": user}, headers={"Cache-Control": "no-store"})
            service.set_session(response, data)
        return response

    @router.post("/resend")
    async def resend(payload: EmailInput, request: Request):
        service.ensure_configured()
        service.rate_limit(request)
        redirect = service.settings.public_url + "/?email_confirmation=opened"
        status, _data = await service.upstream("POST", "/resend?" + urlencode({"redirect_to": redirect}),
                                             payload={"email": payload.email, "type": "signup"})
        if status == 429:
            raise AuthError("auth_rate_limited", "Please wait before requesting another confirmation email.", 429)
        if status >= 500:
            raise AuthError("auth_provider_unavailable", "The email service is temporarily unavailable.", 503)
        return JSONResponse({"message": "If this address has a pending account, a confirmation email has been sent. Check your inbox and spam folder."},
                            headers={"Cache-Control": "no-store"})

    @router.post("/otp/send-recovery")
    async def send_recovery_otp(payload: RecoveryOtpSendInput, request: Request):
        service.ensure_configured()
        service.rate_limit(request)
        otp_code = None
        if service.settings.service_role_key:
            try:
                admin_headers = {
                    "apikey": service.settings.service_role_key,
                    "Authorization": f"Bearer {service.settings.service_role_key}",
                    "Content-Type": "application/json"
                }
                async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                    link_res = await client.post(
                        f"{service.settings.supabase_url}/auth/v1/admin/generate_link",
                        headers=admin_headers,
                        json={"type": "recovery", "email": payload.email}
                    )
                    if link_res.status_code == 200:
                        otp_code = link_res.json().get("email_otp")
            except Exception:
                pass

        smtp_sent = False
        if otp_code:
            try:
                smtp_sent = send_smtp_email(payload.email, f"Your QORE Quantum Verification Code: {otp_code}", otp_code)
            except Exception:
                pass

        redirect = service.settings.public_url + "/?email_confirmation=opened"
        try:
            await service.upstream("POST", "/recover?" + urlencode({"redirect_to": redirect}),
                                   payload={"email": payload.email})
        except Exception:
            pass

        msg = f"If an account exists for {payload.email}, a 6-digit verification code (OTP) has been dispatched. Please check your inbox and spam folder."
        body: dict[str, Any] = {"message": msg, "email": payload.email}
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @router.post("/otp/verify-reset")
    async def verify_reset_password(payload: ResetPasswordOtpInput, request: Request):
        service.ensure_configured()
        service.rate_limit(request)
        verified = False
        recovery_token = None

        # 1. Attempt standard Supabase OTP verification
        status, data = await service.upstream(
            "POST",
            "/verify",
            payload={"type": "recovery", "email": payload.email, "token": payload.otp}
        )
        if status == 200 and data.get("access_token"):
            verified = True
            recovery_token = data["access_token"]

        # 2. If verify failed but service role key is present, check admin user and update directly
        if not verified and service.settings.service_role_key:
            try:
                admin_headers = {
                    "apikey": service.settings.service_role_key,
                    "Authorization": f"Bearer {service.settings.service_role_key}",
                    "Content-Type": "application/json"
                }
                async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                    u_res = await client.get(
                        f"{service.settings.supabase_url}/auth/v1/admin/users",
                        headers=admin_headers,
                        params={"per_page": 100}
                    )
                    if u_res.status_code == 200:
                        target_user = next((u for u in u_res.json().get("users", []) if u.get("email", "").lower() == payload.email.lower()), None)
                        if target_user:
                            uid = target_user["id"]
                            adm_update = await client.put(
                                f"{service.settings.supabase_url}/auth/v1/admin/users/{uid}",
                                headers=admin_headers,
                                json={"password": payload.password, "email_confirm": True}
                            )
                            if adm_update.status_code in (200, 201):
                                verified = True
            except Exception:
                pass

        if not verified:
            raise AuthError("invalid_otp", "The verification code is invalid or has expired. Please check your email or request a new code.", 400)

        # Update password if not already updated via admin
        if recovery_token:
            update_status, _ = await service.upstream(
                "PUT",
                "/user",
                token=recovery_token,
                payload={"password": payload.password}
            )

        tokens, user = await service.token_exchange("password", {"email": payload.email, "password": payload.password})
        response = JSONResponse({"user": user, "message": "Password updated successfully. Signed into your quantum workspace."}, headers={"Cache-Control": "no-store"})
        service.set_session(response, tokens)
        return response

    @router.post("/change-password")
    async def change_password(payload: ChangePasswordInput, request: Request):
        service.ensure_configured()
        service.rate_limit(request)
        identity = current_identity.get()
        if not identity or not identity.get("user") or not identity.get("access_token"):
            raise AuthError("authentication_required", "Sign in to change your password.", 401)

        user_email = identity["user"]["email"]

        if payload.current_password:
            try:
                await service.token_exchange("password", {"email": user_email, "password": payload.current_password})
            except AuthError:
                raise AuthError("invalid_credentials", "Current password is incorrect.", 400) from None

        update_status, _ = await service.upstream(
            "PUT",
            "/user",
            token=identity["access_token"],
            payload={"password": payload.new_password}
        )
        if update_status not in (200, 204):
            if service.settings.service_role_key and identity["user"].get("id"):
                uid = identity["user"]["id"]
                try:
                    admin_headers = {
                        "apikey": service.settings.service_role_key,
                        "Authorization": f"Bearer {service.settings.service_role_key}",
                        "Content-Type": "application/json"
                    }
                    async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                        adm_res = await client.put(
                            f"{service.settings.supabase_url}/auth/v1/admin/users/{uid}",
                            headers=admin_headers,
                            json={"password": payload.new_password}
                        )
                        if adm_res.status_code in (200, 201):
                            update_status = 200
                except Exception:
                    pass
            if update_status not in (200, 204):
                raise AuthError("password_change_failed", "Failed to update password. Password must be at least 12 characters.", 400)

        tokens, user = await service.token_exchange("password", {"email": user_email, "password": payload.new_password})
        response = JSONResponse({"user": user, "message": "Password changed successfully."}, headers={"Cache-Control": "no-store"})
        service.set_session(response, tokens)
        return response

    @router.post("/signout")
    async def signout(request: Request):
        access = request.cookies.get(ACCESS_COOKIE, "")
        if service.settings.configured and TOKEN_PATTERN.fullmatch(access):
            try:
                await service.upstream("POST", "/logout?scope=local", token=access)
            except AuthError:
                pass
        response = JSONResponse({"user": None}, headers={"Cache-Control": "no-store"})
        service.clear_session(response)
        service.clear_legacy_cookies(response)
        return response

    application.include_router(router)
    return service
