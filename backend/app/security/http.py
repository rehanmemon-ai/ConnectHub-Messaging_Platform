import hashlib
import hmac
import secrets
from datetime import UTC, datetime

from fastapi import Request, Response

from app.api.errors import ApiError
from app.core.config import Settings
from app.models import AuthSession


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def session_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_csrf_token(session: AuthSession, settings: Settings) -> str:
    nonce = secrets.token_urlsafe(32)
    signature = _csrf_signature(nonce, session, settings)
    return f"{nonce}.{signature}"


def _csrf_signature(nonce: str, session: AuthSession, settings: Settings) -> str:
    binding = f"{session.id}:{session.token_hash}:{nonce}".encode()
    return hmac.new(settings.require_csrf_secret(), binding, hashlib.sha256).hexdigest()


def verify_csrf_token(token: str, session: AuthSession, settings: Settings) -> bool:
    try:
        nonce, supplied_signature = token.split(".", 1)
    except ValueError:
        return False
    expected_signature = _csrf_signature(nonce, session, settings)
    return bool(nonce and hmac.compare_digest(supplied_signature, expected_signature))


def require_trusted_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin not in settings.allowed_origins:
        raise ApiError(403, "origin_denied", "The request origin is not allowed.")


def require_json_request(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ApiError(400, "json_required", "Content-Type must be application/json.")


def require_csrf(request: Request, session: AuthSession, settings: Settings) -> None:
    require_trusted_origin(request, settings)
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("x-csrf-token")
    if (
        not cookie_token
        or not header_token
        or not hmac.compare_digest(cookie_token, header_token)
        or not verify_csrf_token(cookie_token, session, settings)
    ):
        raise ApiError(403, "csrf_failed", "CSRF validation failed.")


def set_auth_cookies(
    response: Response,
    *,
    raw_session_token: str,
    csrf_token: str,
    expires_at: datetime,
    settings: Settings,
) -> None:
    utc_expires_at = expires_at.astimezone(UTC)
    max_age = max(0, int((utc_expires_at - datetime.now(UTC)).total_seconds()))
    common = {
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": "/",
        "max_age": max_age,
        "expires": utc_expires_at,
    }
    response.set_cookie(
        settings.session_cookie_name,
        raw_session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        **common,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )
