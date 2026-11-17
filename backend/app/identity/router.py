from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import Settings, get_settings
from app.identity.dependencies import CurrentAuth, DatabaseSession
from app.identity.schemas import (
    LoginRequest,
    OwnUser,
    OwnUserEnvelope,
    ProfileUpdateRequest,
    RegisterRequest,
)
from app.identity.service import (
    create_authenticated_session,
    find_live_session,
    register_user,
    revoke_session,
    update_profile,
)
from app.realtime.manager import connection_manager
from app.security.http import (
    clear_auth_cookies,
    new_csrf_token,
    require_csrf,
    require_json_request,
    require_trusted_origin,
    set_auth_cookies,
)
from app.security.rate_limit import rate_limiter

auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _client_key(request: Request, operation: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{operation}:{host}"


@auth_router.post("/register", status_code=201, response_model=OwnUserEnvelope)
async def register(
    data: RegisterRequest,
    request: Request,
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OwnUserEnvelope:
    require_trusted_origin(request, settings)
    require_json_request(request)
    await rate_limiter.check(
        _client_key(request, "register"),
        limit=settings.registration_rate_limit,
        window_seconds=settings.rate_limit_window_seconds,
    )
    user = await register_user(db, data)
    return OwnUserEnvelope(user=OwnUser.model_validate(user))


@auth_router.post("/login", response_model=OwnUserEnvelope)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OwnUserEnvelope:
    require_trusted_origin(request, settings)
    require_json_request(request)
    await rate_limiter.check(
        _client_key(request, "login"),
        limit=settings.login_rate_limit,
        window_seconds=settings.rate_limit_window_seconds,
    )
    created = await create_authenticated_session(
        db,
        identifier=data.identifier,
        password=data.password,
        settings=settings,
    )
    csrf_token = new_csrf_token(created.context.session, settings)
    set_auth_cookies(
        response,
        raw_session_token=created.raw_token,
        csrf_token=csrf_token,
        expires_at=created.context.session.expires_at,
        settings=settings,
    )
    return OwnUserEnvelope(user=OwnUser.model_validate(created.context.user))


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    raw_token = request.cookies.get(settings.session_cookie_name)
    context = await find_live_session(db, raw_token)
    if context is not None:
        require_csrf(request, context.session, settings)
        await revoke_session(db, context)
        await connection_manager.disconnect_session(context.session.id)
    clear_auth_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@users_router.get("/me", response_model=OwnUserEnvelope)
async def get_me(context: CurrentAuth) -> OwnUserEnvelope:
    return OwnUserEnvelope(user=OwnUser.model_validate(context.user))


@users_router.patch("/me", response_model=OwnUserEnvelope)
async def patch_me(
    data: ProfileUpdateRequest,
    request: Request,
    context: CurrentAuth,
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OwnUserEnvelope:
    require_csrf(request, context.session, settings)
    user = await update_profile(db, context, data)
    return OwnUserEnvelope(user=OwnUser.model_validate(user))
