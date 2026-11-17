import asyncio
import os
import selectors
import sys
from collections.abc import AsyncIterator

os.environ.setdefault("CSRF_SECRET", "test-only-csrf-secret-that-is-at-least-32-characters")

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.safety import validate_test_database_url


def _selector_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop(selectors.SelectSelector())


def pytest_asyncio_loop_factories(config, item):  # type: ignore[no-untyped-def]
    """Give async tests the event loop required by Psycopg on Windows."""
    del config, item
    if sys.platform == "win32":
        return {"windows-selector": _selector_loop}
    return {"default": asyncio.new_event_loop}


@pytest.fixture(scope="session")
def migrated_database_url() -> URL:
    settings = get_settings()
    test_url = settings.test_database_url
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is not configured; PostgreSQL integration tests are blocked")

    safe_url = validate_test_database_url(test_url, settings.database_url)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", safe_url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")
    return make_url(safe_url)


@pytest_asyncio.fixture
async def db_session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_database_url, pool_pre_ping=True)
    cleanup = text("""
        TRUNCATE TABLE messages, room_memberships, auth_sessions, rooms, users
        RESTART IDENTITY CASCADE
        """)
    async with engine.begin() as connection:
        await connection.execute(cleanup)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as connection:
        await connection.execute(cleanup)
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    from app.db.session import get_db_session
    from app.main import app
    from app.security.rate_limit import rate_limiter

    async def override_database() -> AsyncIterator[AsyncSession]:
        yield db_session

    await rate_limiter.clear()
    app.dependency_overrides[get_db_session] = override_database
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:5173") as client:
        yield client
    app.dependency_overrides.clear()
    await rate_limiter.clear()
