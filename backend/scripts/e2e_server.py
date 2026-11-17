"""Run ConnectHub on the validated test database for local browser E2E only."""

import asyncio
import os
import selectors
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.safety import validate_test_database_url


async def serve() -> None:
    config = uvicorn.Config(
        "app.main:app", host="127.0.0.1", port=18000, loop="none", log_level="warning"
    )
    await uvicorn.Server(config).serve()


def main() -> None:
    initial = get_settings()
    if initial.test_database_url is None:
        raise RuntimeError("TEST_DATABASE_URL is required for browser E2E tests")
    test_url = validate_test_database_url(initial.test_database_url, initial.database_url)
    os.environ["DATABASE_URL"] = test_url
    os.environ["APP_ENV"] = "test"
    os.environ["ALLOWED_ORIGINS"] = '["http://127.0.0.1:5174"]'
    os.environ["CSRF_SECRET"] = "browser-e2e-only-csrf-secret-value-123456789"
    get_settings.cache_clear()
    if sys.platform == "win32":
        with asyncio.Runner(
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())
        ) as runner:
            runner.run(serve())
        return
    asyncio.run(serve())


if __name__ == "__main__":
    if sys.platform == "win32":
        os.environ.setdefault("PSYCOPG_IMPL", "python")
    main()
