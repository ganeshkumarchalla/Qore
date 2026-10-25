"""Supabase authentication with server-only tokens and verified request identity.

Browser JavaScript receives a public profile, never access or refresh tokens.
The provider owns passwords and Google identity; QORE owns the HTTP-only cookie
boundary and verifies each authenticated identity with the provider's user API.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import secrets
import time
from collections import OrderedDict, deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from http.cookies import CookieError, SimpleCookie
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
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
    "/api/auth/google", "/api/auth/callback", "/api/auth/signin",
    "/api/auth/signup", "/api/auth/signout",
}


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 401):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


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

    @classmethod
    def from_env(cls) -> "AuthSettings":
        url = _origin(os.environ.get("SUPABASE_URL", ""))
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
        public = _origin(os.environ.get("QORE_PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000")
        production = bool(os.environ.get("RENDER")) or os.environ.get("QORE_ENV", "").lower() == "production"
        configured = bool(url and key and public and not _privileged_key(key))
        required = production or configured or os.environ.get("QORE_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}
        return cls(url, key, public, required)

    @property
    def configured(self) -> bool:
        return bool(_origin(self.supabase_url) and self.publishable_key and _origin(self.public_url)
                    and not _privileged_key(self.publishable_key))

    @property
    def secure(self) -> bool:
        return self.public_url.startswith("https://")


class SignInInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=512, repr=False)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


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
            return {"google_enabled": False, "email_enabled": False}
        now = time.monotonic()
        if self._providers and now - self._providers[0] < 30:
            return self._providers[1]
        status, data = await self.upstream("GET", "/settings")
        if status != 200:
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
        external = data.get("external") or {}
        if not isinstance(external, dict):
            raise AuthError("auth_provider_unavailable", "The sign-in service is temporarily unavailable.", 503)
        values = {"google_enabled": external.get("google") is True,
                  "email_enabled": external.get("email", True) is True}
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
        if status != 200 or not isinstance(data.get("access_token"), str) or not isinstance(data.get("refresh_token"), str):
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

    def clear_oauth(self, response: Response) -> None:
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
        if path == "/api/auth/callback":
            # Uvicorn logs the ASGI query string after the response starts.
            # Move one-use codes out of that logged scope before routing.
            raw_query = scope.get("query_string", b"")
            try:
                params = parse_qs(raw_query.decode("utf-8"), keep_blank_values=True, max_num_fields=8) if len(raw_query) <= 8192 else {}
            except (UnicodeError, ValueError):
                params = {}
            scope["state"]["auth_callback_params"] = {key: values[0] for key, values in params.items() if len(values) == 1}
            scope["query_string"] = b""
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
                    response = auth_error_response(AuthError("authentication_required", "Sign in to access your personal workspace."))
                    if resolved.invalid:
                        self.service.clear_session(response)
                    return await response(scope, receive, send)
                if resolved.user:
                    identity = {"owner_id": resolved.user["id"], "user": resolved.user,
                                "access_token": resolved.access_token}
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
                  "google_enabled": False, "email_enabled": False}
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

    @router.get("/google")
    async def google(request: Request):
        service.ensure_configured()
        service.rate_limit(request)
        if not (await service.providers())["google_enabled"]:
            raise AuthError("google_not_enabled", "Google sign-in is not enabled for this project yet.", 503)
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        callback_url = service.settings.public_url + "/api/auth/callback?" + urlencode({"state": state})
        url = service.settings.supabase_url + "/auth/v1/authorize?" + urlencode({
            "provider": "google", "redirect_to": callback_url,
            "code_challenge": challenge, "code_challenge_method": "s256"})
        response = RedirectResponse(url, status_code=303, headers={"Cache-Control": "no-store"})
        for name, value in ((STATE_COOKIE, state), (VERIFIER_COOKIE, verifier)):
            response.set_cookie(name, value, max_age=600, path="/api/auth", httponly=True,
                                secure=service.settings.secure, samesite="lax")
        return response

    @router.get("/callback")
    async def callback(request: Request):
        service.ensure_configured()
        params = getattr(request.state, "auth_callback_params", {})
        query_dict = dict(request.query_params)
        merged = {**query_dict, **params}

        code = (merged.get("code") or "").strip()
        state = (merged.get("state") or "").strip()
        error = (merged.get("error") or "").strip()

        stored = (request.cookies.get(STATE_COOKIE) or "").strip()
        verifier = (request.cookies.get(VERIFIER_COOKIE) or "").strip()

        response = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
        service.clear_oauth(response)

        if error:
            response.headers["location"] = f"/?auth_error={error}"
            return response

        # Validate ASCII pattern for state if present
        if state and not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", state):
            response.headers["location"] = "/?auth_error=signin_failed"
            return response

        if stored and not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", stored):
            response.headers["location"] = "/?auth_error=signin_failed"
            return response

        # If state was echoed back and stored state is present, verify CSRF match
        if state and stored and not secrets.compare_digest(state, stored):
            response.headers["location"] = "/?auth_error=signin_failed"
            return response

        if not code or not verifier or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", verifier) or len(code) > 2048:
            response.headers["location"] = "/?auth_error=signin_failed"
            return response

        try:
            tokens, _user = await service.token_exchange("pkce", {"auth_code": code, "code_verifier": verifier})
            service.set_session(response, tokens)
        except AuthError as err:
            response.headers["location"] = f"/?auth_error={err.code}"
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
        status, data = await service.upstream("POST", "/signup", payload={"email": payload.email,
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
        service.clear_oauth(response)
        return response

    application.include_router(router)
    return service
