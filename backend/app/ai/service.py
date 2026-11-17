import asyncio
import hashlib
import logging
import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.provider import AiProvider, AiProviderError, embedding_profile
from app.ai.schemas import EmbeddingStatus, SummaryView
from app.api.errors import ApiError
from app.core.config import Settings
from app.identity.service import AuthContext
from app.messaging.schemas import MessageView, SemanticMessageResult, SemanticSearchResponse
from app.messaging.service import message_view, require_room_membership
from app.models import AiSummary, EmbeddingJob, Message, MessageEmbedding, User

logger = logging.getLogger(__name__)


def _bounded_summary_input(
    rows: list[tuple[Message, User]], settings: Settings, max_messages: int
) -> tuple[list[tuple[Message, User]], list[str], bool, int]:
    selected = rows[-max_messages:]
    truncated = len(selected) < len(rows)
    remaining = settings.ai_max_summary_characters
    bounded_reversed: list[tuple[Message, User]] = []
    prompt_reversed: list[str] = []
    for message, user in reversed(selected):
        prefix = f"{user.display_name}: "
        transcript_overhead = len("<message></message>\n")
        if remaining <= len(prefix) + transcript_overhead:
            truncated = True
            break
        rendered = prefix + message.content
        available_text = remaining - transcript_overhead
        if len(rendered) > available_text:
            rendered = rendered[:available_text]
            truncated = True
        bounded_reversed.append((message, user))
        prompt_reversed.append(rendered)
        remaining -= len(rendered) + transcript_overhead
        if remaining == 0:
            truncated = True
            break
    bounded = list(reversed(bounded_reversed))
    prompt = list(reversed(prompt_reversed))
    input_characters = sum(len(item) for item in prompt) + 20 * len(prompt) - 1
    return bounded, prompt, truncated, max(0, input_characters)


async def summarize_room(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    *,
    max_messages: int,
    provider: AiProvider,
    settings: Settings,
) -> SummaryView:
    await require_room_membership(db, room_id, context.user.id)
    requested_limit = min(max_messages, settings.ai_max_summary_messages)
    rows = list(
        (
            await db.execute(
                select(Message, User)
                .join(User, User.id == Message.sender_id)
                .where(Message.room_id == room_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(requested_limit + 1)
            )
        ).all()
    )
    if not rows:
        raise ApiError(409, "empty_history", "There are no messages to summarize.")
    rows.reverse()
    bounded_rows, prompt_messages, char_truncated, input_characters = _bounded_summary_input(
        rows, settings, requested_limit
    )
    source_truncated = len(rows) > requested_limit or char_truncated
    fingerprint = hashlib.sha256(
        "|".join(
            [settings.ai_summary_prompt_version]
            + [str(message.id) for message, _ in bounded_rows]
            + [str(input_characters), str(source_truncated)]
        ).encode()
    ).hexdigest()
    cache_filter = (
        AiSummary.room_id == room_id,
        AiSummary.provider == provider.name,
        AiSummary.model == settings.ai_text_model,
        AiSummary.prompt_version == settings.ai_summary_prompt_version,
        AiSummary.source_fingerprint == fingerprint,
    )
    cached = await db.scalar(select(AiSummary).where(*cache_filter))
    if cached is not None:
        return _summary_view(cached, cached=True)
    try:
        content = await provider.summarize(prompt_messages)
    except AiProviderError as error:
        raise ApiError(503, error.code, error.safe_message) from None
    summary = AiSummary(
        room_id=room_id,
        requested_by=context.user.id,
        provider=provider.name,
        model=settings.ai_text_model,
        prompt_version=settings.ai_summary_prompt_version,
        source_fingerprint=fingerprint,
        source_start_id=bounded_rows[0][0].id,
        source_end_id=bounded_rows[-1][0].id,
        source_message_count=len(bounded_rows),
        source_truncated=source_truncated,
        input_characters=input_characters,
        content=content,
    )
    db.add(summary)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        cached = await db.scalar(select(AiSummary).where(*cache_filter))
        if cached is None:
            raise
        return _summary_view(cached, cached=True)
    await db.refresh(summary)
    return _summary_view(summary, cached=False)


def _summary_view(summary: AiSummary, *, cached: bool) -> SummaryView:
    return SummaryView(
        id=summary.id,
        room_id=summary.room_id,
        provider=summary.provider,
        model=summary.model,
        prompt_version=summary.prompt_version,
        content=summary.content,
        source_start_id=summary.source_start_id,
        source_end_id=summary.source_end_id,
        source_message_count=summary.source_message_count,
        source_truncated=summary.source_truncated,
        input_characters=summary.input_characters,
        created_at=summary.created_at,
        cached=cached,
    )


def validate_embedding(vector: list[float], dimensions: int) -> list[float]:
    if len(vector) != dimensions or not vector:
        raise ValueError("Embedding dimensions do not match the active profile")
    normalized = [float(value) for value in vector]
    if not all(math.isfinite(value) for value in normalized):
        raise ValueError("Embedding contains a non-finite value")
    if math.sqrt(sum(value * value for value in normalized)) == 0:
        raise ValueError("Embedding has zero magnitude")
    return normalized


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embedding dimensions do not match")
    if not all(math.isfinite(value) for value in [*left, *right]):
        raise ValueError("Embedding contains a non-finite value")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


async def semantic_search(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    *,
    query: str,
    limit: int,
    provider: AiProvider,
    settings: Settings,
) -> SemanticSearchResponse:
    await require_room_membership(db, room_id, context.user.id)
    profile = embedding_profile(settings)
    try:
        query_vector = validate_embedding(
            await provider.embed_query(query), settings.ai_embedding_dimensions
        )
    except AiProviderError as error:
        raise ApiError(503, error.code, error.safe_message) from None
    except ValueError:
        raise ApiError(
            503, "ai_invalid_response", "The AI provider returned an invalid embedding."
        ) from None
    total = int(
        await db.scalar(select(func.count()).select_from(Message).where(Message.room_id == room_id))
        or 0
    )
    indexed = int(
        await db.scalar(
            select(func.count())
            .select_from(MessageEmbedding)
            .join(Message, Message.id == MessageEmbedding.message_id)
            .where(Message.room_id == room_id, MessageEmbedding.profile == profile)
        )
        or 0
    )
    rows = (
        await db.execute(
            select(MessageEmbedding, Message, User)
            .join(Message, Message.id == MessageEmbedding.message_id)
            .join(User, User.id == Message.sender_id)
            .where(Message.room_id == room_id, MessageEmbedding.profile == profile)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(settings.ai_embedding_candidate_limit)
        )
    ).all()
    scored: list[tuple[float, MessageView]] = []
    for embedding, message, user in rows:
        try:
            vector = validate_embedding(
                [float(value) for value in embedding.embedding], settings.ai_embedding_dimensions
            )
            score = cosine_similarity(query_vector, vector)
        except (TypeError, ValueError):
            logger.warning(
                "Skipped invalid stored embedding", extra={"message_id": str(message.id)}
            )
            continue
        scored.append((score, message_view(message, user)))
    scored.sort(key=lambda item: (item[0], item[1].created_at, item[1].id), reverse=True)
    failed = int(
        await db.scalar(
            select(func.count())
            .select_from(EmbeddingJob)
            .join(Message, Message.id == EmbeddingJob.message_id)
            .where(
                Message.room_id == room_id,
                EmbeddingJob.profile == profile,
                EmbeddingJob.status == "failed",
            )
        )
        or 0
    )
    return SemanticSearchResponse(
        items=[
            SemanticMessageResult(message=message, similarity=round(score, 6))
            for score, message in scored[:limit]
        ],
        total_messages=total,
        indexed_messages=indexed,
        indexed_candidates=len(rows),
        unindexed_messages=max(0, total - indexed),
        candidate_limit=settings.ai_embedding_candidate_limit,
        candidate_window_truncated=indexed > len(rows),
        failed_jobs=failed,
        embedding_profile=profile,
    )


async def embedding_status(
    db: AsyncSession, context: AuthContext, room_id: uuid.UUID, settings: Settings
) -> EmbeddingStatus:
    await require_room_membership(db, room_id, context.user.id)
    profile = embedding_profile(settings)
    total = int(
        await db.scalar(select(func.count()).select_from(Message).where(Message.room_id == room_id))
        or 0
    )
    indexed = int(
        await db.scalar(
            select(func.count())
            .select_from(MessageEmbedding)
            .join(Message, Message.id == MessageEmbedding.message_id)
            .where(Message.room_id == room_id, MessageEmbedding.profile == profile)
        )
        or 0
    )
    status_counts = dict(
        (
            await db.execute(
                select(EmbeddingJob.status, func.count())
                .join(Message, Message.id == EmbeddingJob.message_id)
                .where(Message.room_id == room_id, EmbeddingJob.profile == profile)
                .group_by(EmbeddingJob.status)
            )
        ).all()
    )
    return EmbeddingStatus(
        total_messages=total,
        indexed_messages=indexed,
        pending_jobs=int(status_counts.get("pending", 0) + status_counts.get("processing", 0)),
        failed_jobs=int(status_counts.get("failed", 0)),
        provider=settings.ai_provider,
        model=settings.ai_embedding_model,
        embedding_profile=profile,
        candidate_limit=settings.ai_embedding_candidate_limit,
    )


async def queue_backfill(
    db: AsyncSession,
    context: AuthContext,
    room_id: uuid.UUID,
    limit: int,
    settings: Settings,
) -> int:
    membership = await require_room_membership(db, room_id, context.user.id, lock=True)
    if membership.role != "owner":
        raise ApiError(403, "room_owner_required", "Room owner permission is required.")
    if not settings.ai_enabled:
        raise ApiError(409, "ai_disabled", "AI features are disabled.")
    if not settings.ai_backfill_enabled:
        raise ApiError(409, "ai_backfill_disabled", "AI backfill requires explicit opt-in.")
    profile = embedding_profile(settings)
    message_ids = (
        await db.scalars(
            select(Message.id)
            .outerjoin(
                MessageEmbedding,
                (MessageEmbedding.message_id == Message.id) & (MessageEmbedding.profile == profile),
            )
            .outerjoin(
                EmbeddingJob,
                (EmbeddingJob.message_id == Message.id) & (EmbeddingJob.profile == profile),
            )
            .where(
                Message.room_id == room_id,
                MessageEmbedding.message_id.is_(None),
                EmbeddingJob.message_id.is_(None),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
    ).all()
    for message_id in message_ids:
        db.add(
            EmbeddingJob(
                message_id=message_id,
                status="pending",
                profile=profile,
                origin="backfill",
            )
        )
    await db.commit()
    return len(message_ids)


async def recover_stale_jobs(factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
    profile = embedding_profile(settings)
    async with factory() as db:
        await db.execute(
            update(EmbeddingJob)
            .where(
                EmbeddingJob.profile == profile,
                EmbeddingJob.status == "processing",
                EmbeddingJob.locked_at
                < datetime.now(UTC) - timedelta(seconds=settings.ai_stale_recovery_seconds),
            )
            .values(status="pending", locked_at=None, next_attempt_at=datetime.now(UTC))
        )
        await db.commit()


async def _record_job_failure(
    factory: async_sessionmaker[AsyncSession],
    message_id: uuid.UUID,
    attempts: int,
    code: str,
    settings: Settings,
) -> None:
    async with factory() as db:
        job = await db.get(EmbeddingJob, message_id, with_for_update=True)
        if job is None or job.status != "processing":
            return
        job.last_error_code = code[:64]
        job.locked_at = None
        if attempts >= settings.ai_embedding_max_attempts:
            job.status = "failed"
        else:
            job.status = "pending"
            job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=min(300, 2**attempts))
        await db.commit()


async def _release_cancelled_job(
    factory: async_sessionmaker[AsyncSession], message_id: uuid.UUID
) -> None:
    async with factory() as db:
        job = await db.get(EmbeddingJob, message_id, with_for_update=True)
        if job is None or job.status != "processing":
            return
        job.status = "pending"
        job.locked_at = None
        job.last_error_code = "worker_cancelled"
        job.next_attempt_at = datetime.now(UTC)
        await db.commit()


async def process_one_embedding_job(
    factory: async_sessionmaker[AsyncSession], provider: AiProvider, settings: Settings
) -> bool:
    profile = embedding_profile(settings)
    async with factory() as db:
        job = await db.scalar(
            select(EmbeddingJob)
            .where(
                EmbeddingJob.profile == profile,
                EmbeddingJob.status == "pending",
                EmbeddingJob.next_attempt_at <= datetime.now(UTC),
            )
            .order_by(EmbeddingJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        message = await db.get(Message, job.message_id)
        if message is None:
            await db.delete(job)
            await db.commit()
            return True
        content = message.content
        message_id = message.id
        job.status = "processing"
        job.attempts += 1
        job.locked_at = datetime.now(UTC)
        attempts = job.attempts
        await db.commit()
    try:
        vector = validate_embedding(
            await provider.embed_document(content), settings.ai_embedding_dimensions
        )
    except asyncio.CancelledError:
        await _release_cancelled_job(factory, message_id)
        raise
    except AiProviderError as error:
        await _record_job_failure(factory, message_id, attempts, error.code, settings)
        return True
    except Exception:
        logger.exception("Unexpected embedding job failure", extra={"message_id": str(message_id)})
        await _record_job_failure(
            factory, message_id, attempts, "unexpected_worker_error", settings
        )
        return True
    async with factory() as db:
        current_message = await db.get(Message, message_id)
        if current_message is None:
            job = await db.get(EmbeddingJob, message_id, with_for_update=True)
            if job is not None:
                await db.delete(job)
            await db.commit()
            return True
        await db.execute(
            insert(MessageEmbedding)
            .values(
                message_id=message_id,
                provider=provider.name,
                model=settings.ai_embedding_model,
                profile=profile,
                dimensions=len(vector),
                embedding=vector,
            )
            .on_conflict_do_update(
                index_elements=[MessageEmbedding.message_id],
                set_={
                    "provider": provider.name,
                    "model": settings.ai_embedding_model,
                    "profile": profile,
                    "dimensions": len(vector),
                    "embedding": vector,
                    "updated_at": datetime.now(UTC),
                },
            )
        )
        job = await db.get(EmbeddingJob, message_id, with_for_update=True)
        if job is not None:
            job.status = "completed"
            job.locked_at = None
            job.last_error_code = None
        await db.commit()
    return True
