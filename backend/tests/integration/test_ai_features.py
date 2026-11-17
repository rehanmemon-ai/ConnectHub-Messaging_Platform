import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.provider import AiProviderError, embedding_profile
from app.ai.service import (
    process_one_embedding_job,
    recover_stale_jobs,
    semantic_search,
    summarize_room,
)
from app.core.config import Settings
from app.identity.service import AuthContext
from app.messaging.schemas import SendMessageRequest
from app.messaging.service import send_message
from app.models import AuthSession, EmbeddingJob, MessageEmbedding, Room, User
from app.rooms.schemas import CreateRoomRequest
from app.rooms.service import create_room

pytestmark = pytest.mark.integration


class FakeProvider:
    name = "gemini"

    def __init__(self) -> None:
        self.summary_calls = 0
        self.embedding_calls = 0
        self.fail_code: str | None = None

    async def summarize(self, messages: list[str]) -> str:
        self.summary_calls += 1
        if self.fail_code:
            raise AiProviderError(self.fail_code, "Provider unavailable.")
        return f"Summary of {len(messages)} messages"

    async def _embed(self, text: str) -> list[float]:
        self.embedding_calls += 1
        if self.fail_code:
            raise AiProviderError(self.fail_code, "Provider unavailable.")
        vector = [0.0] * 128
        vector[0] = 1.0 if "python" in text.casefold() else 0.2
        vector[1] = 1.0 if "database" in text.casefold() else 0.1
        return vector

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed(text)

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed(text)


class UnexpectedProvider(FakeProvider):
    async def embed_document(self, text: str) -> list[float]:
        raise RuntimeError("synthetic unexpected failure")


class CancelledProvider(FakeProvider):
    async def embed_document(self, text: str) -> list[float]:
        raise asyncio.CancelledError


async def seeded_context(db: AsyncSession) -> tuple[AuthContext, uuid.UUID]:
    user = User(
        username="alice",
        email="alice@example.test",
        password_hash="argon2-placeholder",
        display_name="Alice",
    )
    session = AuthSession(
        user=user,
        token_hash="a" * 64,
        expires_at=__import__("datetime").datetime(2030, 1, 1, tzinfo=__import__("datetime").UTC),
    )
    db.add_all([user, session])
    await db.flush()
    context = AuthContext(user=user, session=session)
    room = await create_room(db, context, CreateRoomRequest(name="AI Room"))
    return context, room.id


async def test_summary_is_authorized_bounded_and_cached(db_session: AsyncSession) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(ai_embedding_dimensions=128)
    await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Discuss Python"),
        settings,
    )
    await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Discuss databases"),
        settings,
    )
    provider = FakeProvider()
    first = await summarize_room(
        db_session,
        context,
        room_id,
        max_messages=2,
        provider=provider,
        settings=settings,
    )
    second = await summarize_room(
        db_session,
        context,
        room_id,
        max_messages=2,
        provider=provider,
        settings=settings,
    )
    assert first.cached is False
    assert second.cached is True
    assert first.content == second.content == "Summary of 2 messages"
    assert provider.summary_calls == 1
    assert first.prompt_version == settings.ai_summary_prompt_version
    assert first.input_characters <= settings.ai_max_summary_characters


async def test_embedding_worker_persists_and_semantic_search_orders_results(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_auto_embed_new_messages=True,
        ai_embedding_dimensions=128,
    )
    python = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Python async services"),
        settings,
    )
    database = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="PostgreSQL database indexes"),
        settings,
    )
    provider = FakeProvider()
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert await process_one_embedding_job(factory, provider, settings)
    assert await process_one_embedding_job(factory, provider, settings)
    embeddings = (await db_session.scalars(select(MessageEmbedding))).all()
    assert len(embeddings) == 2
    assert all(item.dimensions == 128 for item in embeddings)
    assert all(item.profile == embedding_profile(settings) for item in embeddings)

    result = await semantic_search(
        db_session,
        context,
        room_id,
        query="python",
        limit=2,
        provider=provider,
        settings=settings,
    )
    assert result.items[0].message.id == python.message.id
    assert {item.message.id for item in result.items} == {
        python.message.id,
        database.message.id,
    }
    assert result.total_messages == 2
    assert result.indexed_messages == 2
    assert result.unindexed_messages == 0
    assert result.embedding_profile == embedding_profile(settings)
    await engine.dispose()


async def test_embedding_failure_is_durable_and_does_not_rollback_message(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_auto_embed_new_messages=True,
        ai_embedding_dimensions=128,
        ai_embedding_max_attempts=1,
    )
    sent = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Still persists"),
        settings,
    )
    provider = FakeProvider()
    provider.fail_code = "ai_provider_unavailable"
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert await process_one_embedding_job(factory, provider, settings)
    assert await db_session.get(Room, room_id) is not None
    assert sent.message.id is not None
    await engine.dispose()


async def test_ai_disabled_message_does_not_create_embedding_backlog(
    db_session: AsyncSession,
) -> None:
    context, room_id = await seeded_context(db_session)
    sent = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Private ordinary message"),
        Settings(ai_enabled=False),
    )
    assert await db_session.get(EmbeddingJob, sent.message.id) is None


async def test_unexpected_worker_failure_is_durable_and_bounded(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_auto_embed_new_messages=True,
        ai_embedding_dimensions=128,
        ai_embedding_max_attempts=1,
    )
    sent = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Message survives worker failure"),
        settings,
    )
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert await process_one_embedding_job(factory, UnexpectedProvider(), settings)
    await db_session.refresh(await db_session.get(EmbeddingJob, sent.message.id))
    job = await db_session.get(EmbeddingJob, sent.message.id)
    assert job is not None
    assert job.status == "failed"
    assert job.last_error_code == "unexpected_worker_error"
    assert job.locked_at is None
    await engine.dispose()


async def test_stale_worker_job_is_recovered_without_timing_sleep(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_auto_embed_new_messages=True,
        ai_embedding_dimensions=128,
        ai_stale_recovery_seconds=10,
    )
    sent = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Recover this job"),
        settings,
    )
    job = await db_session.get(EmbeddingJob, sent.message.id)
    assert job is not None
    job.status = "processing"
    job.locked_at = datetime.now(UTC) - timedelta(seconds=30)
    await db_session.commit()
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    await recover_stale_jobs(factory, settings)
    await db_session.refresh(job)
    assert job.status == "pending"
    assert job.locked_at is None
    await engine.dispose()


async def test_worker_cancellation_releases_claim_for_restart(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_auto_embed_new_messages=True,
        ai_embedding_dimensions=128,
    )
    sent = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Cancellation-safe job"),
        settings,
    )
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with pytest.raises(asyncio.CancelledError):
        await process_one_embedding_job(factory, CancelledProvider(), settings)
    job = await db_session.get(EmbeddingJob, sent.message.id)
    assert job is not None
    await db_session.refresh(job)
    assert job.status == "pending"
    assert job.locked_at is None
    assert job.last_error_code == "worker_cancelled"
    await engine.dispose()


async def test_transient_provider_failure_retries_then_completes(
    db_session: AsyncSession, migrated_database_url: URL
) -> None:
    context, room_id = await seeded_context(db_session)
    settings = Settings(
        ai_enabled=True,
        ai_api_key="x" * 40,
        ai_auto_embed_new_messages=True,
        ai_embedding_dimensions=128,
        ai_embedding_max_attempts=2,
    )
    sent = await send_message(
        db_session,
        context,
        room_id,
        SendMessageRequest(client_id=uuid.uuid4(), content="Python retry"),
        settings,
    )
    provider = FakeProvider()
    provider.fail_code = "ai_provider_unavailable"
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    assert await process_one_embedding_job(factory, provider, settings)
    job = await db_session.get(EmbeddingJob, sent.message.id)
    assert job is not None
    await db_session.refresh(job)
    assert job.status == "pending"
    job.next_attempt_at = datetime.now(UTC)
    await db_session.commit()
    provider.fail_code = None
    assert await process_one_embedding_job(factory, provider, settings)
    await db_session.refresh(job)
    assert job.status == "completed"
    assert await db_session.get(MessageEmbedding, sent.message.id) is not None
    await engine.dispose()
