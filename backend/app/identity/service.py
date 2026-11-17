from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.config import Settings
from app.identity.schemas import ProfileUpdateRequest, RegisterRequest
from app.models import AuthSession, User
from app.security.http import new_session_token, session_token_digest
from app.security.passwords import hash_password, password_needs_rehash, verify_password


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    session: AuthSession


@dataclass(frozen=True, slots=True)
class CreatedSession:
    context: AuthContext
    raw_token: str


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    model = User(
        username=data.username,
        email=str(data.email),
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(model)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        constraint = _constraint_name(error)
        if constraint == "uq_users_username_ci":
            raise ApiError(409, "username_taken", "That username is already in use.") from None
        if constraint == "uq_users_email_ci":
            raise ApiError(409, "email_taken", "That email is already in use.") from None
        raise
    await db.refresh(model)
    return model


async def create_authenticated_session(
    db: AsyncSession,
    *,
    identifier: str,
    password: str,
    settings: Settings,
) -> CreatedSession:
    user = await db.scalar(
        select(User).where(
            or_(func.lower(User.username) == identifier, func.lower(User.email) == identifier)
        )
    )
    valid = verify_password(user.password_hash if user else None, password)
    if not user or not valid:
        raise ApiError(401, "invalid_credentials", "The username/email or password is invalid.")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    raw_token = new_session_token()
    now = datetime.now(UTC)
    session = AuthSession(
        user_id=user.id,
        token_hash=session_token_digest(raw_token),
        created_at=now,
        expires_at=now + timedelta(days=settings.session_lifetime_days),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return CreatedSession(AuthContext(user=user, session=session), raw_token)


async def find_live_session(db: AsyncSession, raw_token: str | None) -> AuthContext | None:
    if not raw_token or len(raw_token) > 512:
        return None
    digest = session_token_digest(raw_token)
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.token_hash == digest,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return AuthContext(user=row[1], session=row[0])


async def revoke_session(db: AsyncSession, context: AuthContext) -> None:
    context.session.revoked_at = datetime.now(UTC)
    await db.commit()


async def update_profile(
    db: AsyncSession, context: AuthContext, data: ProfileUpdateRequest
) -> User:
    if data.username is not None:
        context.user.username = data.username
    if data.display_name is not None:
        context.user.display_name = data.display_name
    context.user.updated_at = datetime.now(UTC)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if _constraint_name(error) == "uq_users_username_ci":
            raise ApiError(409, "username_taken", "That username is already in use.") from None
        raise
    await db.refresh(context.user)
    return context.user
