import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai.router import router as ai_router
from app.ai.worker import embedding_worker
from app.api.errors import (
    ApiError,
    api_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_context
from app.db.session import dispose_engine, get_engine
from app.identity.router import auth_router, users_router
from app.messaging.router import router as messaging_router
from app.notifications.router import router as notifications_router
from app.realtime.manager import connection_manager
from app.realtime.router import router as realtime_router
from app.rooms.router import invitations_router, rooms_router, user_rooms_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def check_database_readiness() -> bool:
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        # Deliberately omit exception detail: connection errors can contain credentials.
        logger.warning("Database readiness check failed")
        return False
    return True


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.require_csrf_secret()
    logger.info("ConnectHub backend starting")
    worker = None
    if settings.ai_enabled and settings.ai_api_key is not None:
        worker = asyncio.create_task(embedding_worker(settings))
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        await connection_manager.shutdown()
    await dispose_engine()
    logger.info("ConnectHub backend stopped")


app = FastAPI(title="ConnectHub API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unexpected_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rooms_router)
app.include_router(user_rooms_router)
app.include_router(invitations_router)
app.include_router(messaging_router)
app.include_router(notifications_router)
app.include_router(ai_router)
app.include_router(realtime_router)


@app.middleware("http")
async def add_request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(uuid.uuid4())
    token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "frame-ancestors 'none'; form-action 'self'; "
                "script-src 'self'; style-src 'self'; connect-src 'self'; "
                "img-src 'self' data:; font-src 'self'"
            )
        return response
    finally:
        request_id_context.reset(token)


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> JSONResponse:
    if await check_database_readiness():
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not_ready"})
