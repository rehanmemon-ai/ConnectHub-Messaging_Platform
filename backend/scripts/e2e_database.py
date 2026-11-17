"""Safely prepare or clean the dedicated PostgreSQL browser-test database."""

import asyncio
import selectors
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.safety import validate_test_database_url


async def clean() -> None:
    settings = get_settings()
    if settings.test_database_url is None:
        raise RuntimeError("TEST_DATABASE_URL is required for browser E2E tests")
    safe_url = validate_test_database_url(settings.test_database_url, settings.database_url)
    engine = create_async_engine(safe_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            database_name = await connection.scalar(text("SELECT current_database()"))
            if not isinstance(database_name, str) or not database_name.endswith("_test"):
                raise RuntimeError("Refusing to clean a database whose name does not end in _test")
            await connection.execute(
                text(
                    "TRUNCATE TABLE messages, room_memberships, auth_sessions, rooms, users "
                    "RESTART IDENTITY CASCADE"
                )
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.argv[1:] != ["clean"]:
        raise SystemExit("Usage: python scripts/e2e_database.py clean")
    if sys.platform == "win32":
        with asyncio.Runner(
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        ) as runner:
            runner.run(clean())
    else:
        asyncio.run(clean())
