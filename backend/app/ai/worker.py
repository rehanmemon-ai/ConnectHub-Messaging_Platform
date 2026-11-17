import asyncio
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.provider import build_provider
from app.ai.service import process_one_embedding_job, recover_stale_jobs
from app.core.config import Settings
from app.db.session import get_engine

logger = logging.getLogger(__name__)


async def embedding_worker(settings: Settings) -> None:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    provider = build_provider(settings)
    await recover_stale_jobs(factory, settings)
    last_recovery = time.monotonic()
    while True:
        if time.monotonic() - last_recovery >= settings.ai_stale_recovery_seconds:
            await recover_stale_jobs(factory, settings)
            last_recovery = time.monotonic()
        try:
            processed = await process_one_embedding_job(factory, provider, settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Embedding worker iteration failed")
            processed = False
        if not processed:
            await asyncio.sleep(settings.ai_worker_poll_seconds)
