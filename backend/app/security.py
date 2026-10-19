"""Access control, rate limiting, request limits, security headers and secret redaction.

Public visitors can read everything a finished study shows. Starting runs, editing data, Review and Settings
need the access code (ADMIN_ACCESS_CODE). The code is compared as a salted scrypt hash, and a successful
unlock sets a signed, httpOnly, SameSite=Strict session cookie.

State (rate-limit buckets, failed attempts) is in memory. That is correct because the app runs as a single
worker process: the run manager and its SSE event log are in memory too (see docs/DEPLOY.md).
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.config import Settings, get_settings

COOKIE = "vab_session"
log = logging.getLogger("vetagentbench")


# ---------- redaction ----------

_KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),  # Google API keys
    re.compile(r"\bAQ\.[0-9A-Za-z_\-.]{20,}"),  # Google OAuth-style access tokens
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),  # OpenAI-style keys
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)((?:api[_-]?key|key|token|secret)=)[^&\s\"']{8,}"),
]


def redact(text: str, settings: Settings | None = None) -> str:
    """Remove configured secrets and anything shaped like an API key."""
    if not text:
        return text
    s = settings or get_settings()
    for value in s.secrets:
        text = text.replace(value, "[redacted]")
    for pat in _KEY_PATTERNS:
        text = pat.sub(lambda m: (m.group(1) if m.groups() else "") + "[redacted]", text)
    return text


_factory_installed = False


def install_log_redaction() -> None:
    """Redact every log record at creation, whichever logger or handler it goes through, and give the app
    logger a handler when the server has not configured one."""
    global _factory_installed
    if not _factory_installed:
        base = logging.getLogRecordFactory()

        def factory(*args, **kwargs):
            record = base(*args, **kwargs)
            try:
                msg = record.getMessage()
            except Exception:
                return record
            clean = redact(msg)
            if clean != msg:
                record.msg, record.args = clean, None
            if record.exc_text:
                record.exc_text = redact(record.exc_text)
            return record

        logging.setLogRecordFactory(factory)
        _factory_installed = True
    app_log = logging.getLogger("vetagentbench")
    if not app_log.handlers and not logging.getLogger().handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        app_log.addHandler(h)
    app_log.setLevel(logging.INFO)
    # httpx logs full request URLs at INFO; keep it quiet so URLs with query keys never reach the log.
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ---------- access code and session ----------

_SALT = secrets.token_bytes(16)
_hash_cache: dict[str, bytes] = {}


def _scrypt(code: str) -> bytes:
    return hashlib.scrypt(code.encode("utf-8"), salt=_SALT, n=2**14, r=8, p=1, dklen=32)


def _configured_hash(settings: Settings) -> bytes | None:
    code = settings.admin_access_code.strip()
    if not code:
        return None
    # Keep only the hash in memory beyond the settings object; computed once per code.
    fp = hashlib.sha256(code.encode()).hexdigest()
    if fp not in _hash_cache:
        _hash_cache.clear()
        _hash_cache[fp] = _scrypt(code)
    return _hash_cache[fp]


def check_code(candidate: str, settings: Settings) -> bool:
    expected = _configured_hash(settings)
    if expected is None or not candidate or len(candidate) > 256:
        return False
    return hmac.compare_digest(_scrypt(candidate), expected)


def _signing_key(settings: Settings) -> bytes:
    secret = settings.session_secret.strip()
    if secret:
        return hashlib.sha256(b"vab-session:" + secret.encode()).digest()
    # No SESSION_SECRET: derive from the access code, so sessions survive restarts and end when the code changes.
    return hashlib.sha256(b"vab-session-from-code:" + settings.admin_access_code.strip().encode()).digest()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_session(settings: Settings, now: float | None = None) -> str:
    exp = int((now or time.time()) + settings.session_hours * 3600)
    body = _b64(json.dumps({"r": "admin", "exp": exp, "n": secrets.token_hex(8)}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_signing_key(settings), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_session(token: str | None, settings: Settings, now: float | None = None) -> bool:
    if not token or "." not in token or len(token) > 512 or not settings.admin_access_code.strip():
        return False
    body, sig = token.rsplit(".", 1)
    good = _b64(hmac.new(_signing_key(settings), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, good):
        return False
    try:
        data = json.loads(_unb64(body))
    except ValueError:
        return False
    return data.get("r") == "admin" and int(data.get("exp", 0)) > (now or time.time())


def is_admin(request: Request, settings: Settings) -> bool:
    if not settings.access_required:
        return True  # local development with no access code configured
    return read_session(request.cookies.get(COOKIE), settings)


def require_admin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if not is_admin(request, settings):
        raise HTTPException(
            status_code=401,
            detail="Read-only mode. Enter the access code to run cases, edit data, review or change settings.",
        )


def set_session_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        COOKIE, make_session(settings), max_age=settings.session_hours * 3600, httponly=True,
        secure=settings.secure_cookies, samesite="strict", path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=settings.secure_cookies, samesite="strict")


# ---------- lockout after repeated wrong codes ----------

GLOBAL_FAILURE_FACTOR = 6  # this many times the per-IP limit, from all IPs together, locks everyone out


@dataclass
class _Failures:
    times: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0


class Lockout:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_ip: dict[str, _Failures] = {}
        self._global = _Failures()

    def reset(self) -> None:
        with self._lock:
            self._by_ip.clear()
            self._global = _Failures()

    def locked_for(self, ip: str, settings: Settings, now: float | None = None) -> int:
        """Seconds until this IP may try again (0 = not locked)."""
        t = now or time.time()
        with self._lock:
            f = self._by_ip.get(ip)
            until = max(f.locked_until if f else 0.0, self._global.locked_until)
        return max(0, int(until - t + 0.999))

    def fail(self, ip: str, settings: Settings, now: float | None = None) -> int:
        """Record a wrong code. Returns attempts left before lockout (0 = now locked)."""
        t = now or time.time()
        window = settings.auth_lockout_minutes * 60
        with self._lock:
            f = self._by_ip.setdefault(ip, _Failures())
            for rec, limit in ((f, settings.auth_max_attempts), (self._global, settings.auth_max_attempts * GLOBAL_FAILURE_FACTOR)):
                rec.times.append(t)
                while rec.times and rec.times[0] < t - window:
                    rec.times.popleft()
                if len(rec.times) >= limit:
                    rec.locked_until = t + window
                    rec.times.clear()
            left = settings.auth_max_attempts - len(f.times)
            return 0 if f.locked_until > t else left

    def succeed(self, ip: str) -> None:
        with self._lock:
            self._by_ip.pop(ip, None)


lockout = Lockout()


# ---------- rate limit ----------

class RateLimiter:
    """Sliding one-minute window per client IP."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def hit(self, key: str, limit: int, now: float | None = None) -> int:
        """Record a request; returns seconds to wait (0 = allowed)."""
        t = now or time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= t - 60:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(q[0] + 60 - t + 0.999))
            q.append(t)
            if len(self._hits) > 50_000:  # bound memory under a flood of distinct IPs
                for k in [k for k, v in self._hits.items() if not v][:10_000]:
                    del self._hits[k]
            return 0


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    # Uvicorn/gunicorn resolve X-Forwarded-For only from trusted proxies (FORWARDED_ALLOW_IPS), so this is
    # the real client behind the platform's load balancer and cannot be spoofed by a direct caller.
    return request.client.host if request.client else "unknown"


# ---------- middleware ----------

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'; manifest-src 'self'"
)

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class GuardMiddleware(BaseHTTPMiddleware):
    """Rate limit, body-size limit, same-origin check for writes, security headers."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        if path.startswith("/api/"):
            # Health is exempt so platform health checks never trip the limit.
            if path != "/api/health":
                wait = rate_limiter.hit(client_ip(request), settings.rate_limit_per_minute)
                if wait:
                    return self._headers(JSONResponse(
                        status_code=429,
                        content={"detail": f"Too many requests. Try again in {wait} s."},
                        headers={"Retry-After": str(wait)},
                    ), settings)
            if request.method in UNSAFE:
                length = request.headers.get("content-length")
                if length is not None and (not length.isdigit() or int(length) > settings.max_body_bytes):
                    return self._headers(JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body too large (limit {settings.max_body_bytes:,} bytes)."},
                    ), settings)
                if not self._same_origin(request, settings):
                    return self._headers(JSONResponse(status_code=403, content={"detail": "Cross-origin request refused."}), settings)
        response = await call_next(request)
        return self._headers(response, settings)

    @staticmethod
    def _same_origin(request: Request, settings: Settings) -> bool:
        origin = request.headers.get("origin")
        if not origin:
            return True  # non-browser clients (curl, tests); the cookie is SameSite=Strict anyway
        origin = origin.rstrip("/")
        host = request.headers.get("host", "")
        if origin in settings.origins:
            return True
        return origin.split("://", 1)[-1] == host

    @staticmethod
    def _headers(response: Response, settings: Settings) -> Response:
        h = response.headers
        h.setdefault("Content-Security-Policy", CSP)
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), interest-cohort=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("X-Robots-Tag", "noindex, nofollow")
        if settings.is_production:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class BodySizeLimit:
    """Pure ASGI guard: stop reading a request body past MAX_BODY_BYTES, even when it is sent chunked."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = get_settings().max_body_bytes
        seen = 0

        async def limited_receive():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            response = JSONResponse(status_code=413, content={"detail": f"Request body too large (limit {limit:,} bytes)."})
            await response(scope, receive, send)


class _TooLarge(Exception):
    pass
