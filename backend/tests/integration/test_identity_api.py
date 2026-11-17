import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.main import app
from app.models import AuthSession, User
from app.security.passwords import verify_password

pytestmark = pytest.mark.integration

ORIGIN = {"Origin": "http://localhost:5173"}
PASSWORD = "correct horse battery staple"


async def register(
    client: AsyncClient,
    *,
    username: str = "Alice",
    email: str = "Alice@Example.test",
    password: str = PASSWORD,
    display_name: str = " Alice ",
):
    return await client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )


async def login(client: AsyncClient, identifier: str = "alice", password: str = PASSWORD):
    return await client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"identifier": identifier, "password": password},
    )


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": client.cookies["connecthub_csrf"]}


async def test_registration_hashes_password_normalizes_and_hides_internal_fields(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await register(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["email"] == "alice@example.test"
    assert body["user"]["display_name"] == "Alice"
    assert "password" not in str(body).lower()
    user = await db_session.scalar(select(User).where(User.username == "alice"))
    assert user is not None
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(user.password_hash, PASSWORD)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "username": "alice",
            "email": "not-an-email",
            "password": PASSWORD,
            "display_name": "Alice",
        },
        {
            "username": "with space",
            "email": "a@example.test",
            "password": PASSWORD,
            "display_name": "Alice",
        },
        {
            "username": "alice",
            "email": "a@example.test",
            "password": "short",
            "display_name": "Alice",
        },
        {
            "username": "alice",
            "email": "a@example.test",
            "password": PASSWORD,
            "display_name": "Alice",
            "role": "owner",
        },
    ],
)
async def test_registration_rejects_invalid_or_unknown_fields(
    api_client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await api_client.post("/api/v1/auth/register", headers=ORIGIN, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_registration_uses_database_case_insensitive_conflicts(
    api_client: AsyncClient,
) -> None:
    assert (await register(api_client)).status_code == 201
    username_conflict = await register(api_client, username="ALICE", email="other@example.test")
    email_conflict = await register(api_client, username="bob", email="ALICE@example.test")
    assert username_conflict.status_code == 409
    assert username_conflict.json()["error"]["code"] == "username_taken"
    assert email_conflict.status_code == 409
    assert email_conflict.json()["error"]["code"] == "email_taken"


async def test_registration_and_login_require_trusted_origin(api_client: AsyncClient) -> None:
    payload = {
        "username": "alice",
        "email": "a@example.test",
        "password": PASSWORD,
        "display_name": "Alice",
    }
    denied = await api_client.post(
        "/api/v1/auth/register", headers={"Origin": "https://evil.example"}, json=payload
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "origin_denied"


async def test_login_sets_secure_shapes_and_stores_only_digest(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(api_client)
    response = await login(api_client, "ALICE@EXAMPLE.TEST")

    assert response.status_code == 200
    assert "token" not in str(response.json()).lower()
    cookies = response.headers.get_list("set-cookie")
    session_header = next(value for value in cookies if value.startswith("connecthub_session="))
    csrf_header = next(value for value in cookies if value.startswith("connecthub_csrf="))
    assert "HttpOnly" in session_header
    assert "SameSite=lax" in session_header
    assert "HttpOnly" not in csrf_header
    raw_token = api_client.cookies["connecthub_session"]
    stored = await db_session.scalar(select(AuthSession))
    assert stored is not None
    assert stored.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
    assert stored.token_hash != raw_token


async def test_invalid_login_is_generic_and_does_not_create_session(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(api_client)
    wrong_password = await login(api_client, password="wrong password")
    unknown_user = await login(api_client, identifier="nobody")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"
    assert unknown_user.json()["error"]["code"] == "invalid_credentials"
    assert await db_session.scalar(select(AuthSession.id)) is None


async def test_authenticated_profile_and_csrf_protected_update(api_client: AsyncClient) -> None:
    await register(api_client)
    await login(api_client)

    profile = await api_client.get("/api/v1/users/me")
    missing_csrf = await api_client.patch(
        "/api/v1/users/me", headers=ORIGIN, json={"display_name": "Alice Updated"}
    )
    updated = await api_client.patch(
        "/api/v1/users/me",
        headers=csrf_headers(api_client),
        json={"display_name": " Alice Updated "},
    )
    assert profile.status_code == 200
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "csrf_failed"
    assert updated.status_code == 200
    assert updated.json()["user"]["display_name"] == "Alice Updated"


@pytest.mark.parametrize("state", ["expired", "revoked"])
async def test_expired_and_revoked_sessions_are_rejected(
    api_client: AsyncClient, db_session: AsyncSession, state: str
) -> None:
    await register(api_client)
    await login(api_client)
    session = await db_session.scalar(select(AuthSession))
    assert session is not None
    if state == "expired":
        now = datetime.now(UTC)
        session.created_at = now - timedelta(seconds=2)
        session.expires_at = now - timedelta(seconds=1)
    else:
        session.revoked_at = datetime.now(UTC)
    await db_session.commit()

    response = await api_client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


async def test_malformed_and_unknown_session_cookies_are_safe(api_client: AsyncClient) -> None:
    api_client.cookies.set("connecthub_session", "x" * 600)
    malformed = await api_client.get("/api/v1/users/me")
    api_client.cookies.set("connecthub_session", "unknown-session")
    unknown = await api_client.get("/api/v1/users/me")
    assert malformed.status_code == unknown.status_code == 401


async def test_logout_requires_csrf_for_live_session_then_revokes_and_is_idempotent(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(api_client)
    await login(api_client)
    denied = await api_client.post("/api/v1/auth/logout", headers=ORIGIN)
    assert denied.status_code == 403

    response = await api_client.post("/api/v1/auth/logout", headers=csrf_headers(api_client))
    assert response.status_code == 204
    session = await db_session.scalar(select(AuthSession))
    assert session is not None and session.revoked_at is not None
    assert any("Max-Age=0" in value for value in response.headers.get_list("set-cookie"))
    again = await api_client.post("/api/v1/auth/logout")
    assert again.status_code == 204


async def test_revoking_one_device_session_does_not_revoke_another(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(api_client)
    await login(api_client)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:5173"
    ) as second_device:
        assert (await login(second_device)).status_code == 200
        assert (await second_device.get("/api/v1/users/me")).status_code == 200

        first_logout = await api_client.post(
            "/api/v1/auth/logout", headers=csrf_headers(api_client)
        )
        assert first_logout.status_code == 204
        assert (await api_client.get("/api/v1/users/me")).status_code == 401
        assert (await second_device.get("/api/v1/users/me")).status_code == 200

    sessions = (await db_session.scalars(select(AuthSession))).all()
    assert len(sessions) == 2
    assert sum(session.revoked_at is not None for session in sessions) == 1


async def test_registration_rate_limit_returns_retry_after(api_client: AsyncClient) -> None:
    base = get_settings()
    limited = Settings(
        **{
            **base.model_dump(),
            "csrf_secret": base.csrf_secret,
            "registration_rate_limit": 1,
        }
    )
    app.dependency_overrides[get_settings] = lambda: limited
    try:
        assert (await register(api_client)).status_code == 201
        limited_response = await register(
            api_client, username="bob", email="bob@example.test", display_name="Bob"
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert limited_response.status_code == 429
    assert limited_response.json()["error"]["code"] == "rate_limited"
    assert int(limited_response.headers["retry-after"]) >= 1
