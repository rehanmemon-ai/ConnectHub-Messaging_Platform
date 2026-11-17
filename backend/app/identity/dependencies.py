from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.identity.service import AuthContext, find_live_session

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


async def get_optional_auth(
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
) -> AuthContext | None:
    token = request.cookies.get(settings.session_cookie_name)
    return await find_live_session(db, token)


async def get_current_auth(
    context: Annotated[AuthContext | None, Depends(get_optional_auth)],
) -> AuthContext:
    if context is None:
        raise ApiError(401, "authentication_required", "Authentication is required.")
    return context


CurrentAuth = Annotated[AuthContext, Depends(get_current_auth)]
