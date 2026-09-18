"""Application security helpers for English Practice Hub.

This module intentionally avoids external stateful security services so the
existing Docker deployment remains simple. It provides CSRF protection,
security headers, host/HTTPS guards, request IDs and a lightweight login
throttle. For internet-facing deployments, place the app behind a reverse
proxy and complement this with infrastructure-level rate limiting.
"""

from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta

from flask import abort, g, jsonify, render_template, request, session
from markupsafe import Markup, escape
from werkzeug.middleware.proxy_fix import ProxyFix


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_LOGIN_FAILURES: dict[str, deque[float]] = defaultdict(deque)
_LOGIN_LOCK = threading.Lock()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def csrf_input() -> Markup:
    token = escape(get_csrf_token())
    return Markup(f'<input type="hidden" name="_csrf_token" value="{token}">')


def _csrf_error(message: str = "The security token is missing or expired."):
    if request.path.startswith("/game/api/") or request.path.startswith("/api/") or request.is_json:
        return jsonify({"ok": False, "error": message}), 400
    return render_template(
        "error.html",
        status_code=400,
        title="Request expired",
        message="Please reload the page and try again.",
        request_id=getattr(g, "request_id", None),
    ), 400


def _validate_csrf():
    if request.method in SAFE_METHODS:
        return None

    expected = session.get("_csrf_token")
    supplied = (
        request.form.get("_csrf_token")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
    )
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        return _csrf_error()
    return None


def _validate_host():
    raw = (os.getenv("ALLOWED_HOSTS") or "").strip()
    if not raw:
        return None
    allowed = {item.strip().lower() for item in raw.split(",") if item.strip()}
    if "*" in allowed:
        return None
    host = (request.host or "").split(":", 1)[0].strip("[]").lower()
    if host not in allowed:
        abort(400, description="Invalid host header.")
    return None


def _force_https():
    if not _env_bool("FORCE_HTTPS", False):
        return None
    if request.is_secure:
        return None
    # Health endpoints remain usable inside a container/network.
    if request.path in {"/healthz", "/readyz"}:
        return None
    from flask import redirect

    return redirect(request.url.replace("http://", "https://", 1), code=308)


def client_ip() -> str:
    # ProxyFix normalizes remote_addr when TRUST_PROXY is enabled.
    return request.remote_addr or "unknown"


def _login_key(username: str) -> str:
    return f"{client_ip()}|{(username or '').strip().lower()}"


def login_is_rate_limited(username: str) -> tuple[bool, int]:
    limit = max(3, int(os.getenv("LOGIN_MAX_FAILURES", "8")))
    window = max(60, int(os.getenv("LOGIN_FAILURE_WINDOW_SECONDS", "900")))
    now = time.monotonic()
    key = _login_key(username)
    with _LOGIN_LOCK:
        events = _LOGIN_FAILURES[key]
        while events and now - events[0] > window:
            events.popleft()
        if len(events) >= limit:
            retry = max(1, int(window - (now - events[0])))
            return True, retry
    return False, 0


def record_login_failure(username: str) -> None:
    key = _login_key(username)
    with _LOGIN_LOCK:
        _LOGIN_FAILURES[key].append(time.monotonic())


def clear_login_failures(username: str) -> None:
    key = _login_key(username)
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(key, None)


def password_policy_error(password: str) -> str | None:
    value = password or ""
    if len(value) < 10:
        return "Password must contain at least 10 characters."
    categories = sum(
        [
            any(ch.islower() for ch in value),
            any(ch.isupper() for ch in value),
            any(ch.isdigit() for ch in value),
            any(not ch.isalnum() for ch in value),
        ]
    )
    if categories < 3:
        return "Password must include at least three of: lowercase, uppercase, number, symbol."
    return None


def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), camera=(), microphone=(self)",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "; ".join(
            [
                "default-src 'self'",
                "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'",
                "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'",
                "font-src 'self' https://cdn.jsdelivr.net data:",
                "img-src 'self' data: blob:",
                "connect-src 'self'",
                "media-src 'self' data: blob:",
                "frame-src https://www.youtube-nocookie.com",
                "object-src 'none'",
                "base-uri 'self'",
                "frame-ancestors 'none'",
                "form-action 'self'",
            ]
        ),
    )
    if request.is_secure or _env_bool("FORCE_HTTPS", False):
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    if getattr(g, "request_id", None):
        response.headers.setdefault("X-Request-ID", g.request_id)
    if session.get("_user_id") and response.mimetype == "text/html":
        response.headers.setdefault("Cache-Control", "no-store, private")
        response.headers.setdefault("Pragma", "no-cache")
    return response


def init_security(app):
    if _env_bool("TRUST_PROXY", False):
        # One reverse-proxy hop (Nginx, Cloudflare Tunnel, ngrok, etc.).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    app.config.setdefault("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    production = (os.getenv("APP_ENV") or "development").strip().lower() == "production"
    app.config["SESSION_COOKIE_SECURE"] = _env_bool("SESSION_COOKIE_SECURE", production)
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(hours=12))

    @app.before_request
    def security_before_request():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        host_result = _validate_host()
        if host_result is not None:
            return host_result
        https_result = _force_https()
        if https_result is not None:
            return https_result
        return _validate_csrf()

    @app.after_request
    def security_after_request(response):
        return _security_headers(response)

    @app.context_processor
    def inject_security_helpers():
        return {
            "csrf_token": get_csrf_token,
            "csrf_input": csrf_input,
        }
