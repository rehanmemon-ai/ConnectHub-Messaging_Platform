"""Versioned synthetic retrieval corpus and relevance judgments.

No fixture is derived from a real ConnectHub conversation. The construction is
deterministic and intentionally includes paraphrases, distractors, and old
relevant messages followed by newer irrelevant messages.
"""

from dataclasses import dataclass

DATASET_VERSION = "connecthub-synthetic-retrieval-v1"


@dataclass(frozen=True, slots=True)
class EvalMessage:
    id: str
    room: str
    text: str
    topic: str
    sequence: int


@dataclass(frozen=True, slots=True)
class EvalQuery:
    id: str
    text: str
    relevance: dict[str, int]
    category: str


TOPICS = (
    (
        "database-index",
        "backend",
        "PostgreSQL needs a composite index on room_id and created_at",
        "database index",
        "speed up message history",
    ),
    (
        "session-expiry",
        "security",
        "Opaque sessions expire after seven days and are stored as digests",
        "session expiry",
        "when does login access end",
    ),
    (
        "websocket-heartbeat",
        "realtime",
        "WebSocket clients send heartbeat pings before the idle timeout",
        "heartbeat ping",
        "keep the live connection alive",
    ),
    (
        "private-invite",
        "product",
        "Private rooms require an invitation before membership is created",
        "private invitation",
        "how someone enters a hidden room",
    ),
    (
        "backup-restore",
        "operations",
        "The backup archive must be restored into an isolated restore-test database",
        "restore rehearsal",
        "prove the backup can recover data",
    ),
    (
        "csrf-cookie",
        "security",
        "State-changing requests require a CSRF header matching the signed cookie",
        "CSRF cookie",
        "protect browser writes from forged requests",
    ),
    (
        "message-retry",
        "realtime",
        "Client-generated UUIDs make message retries idempotent",
        "idempotent retry",
        "avoid duplicate messages after reconnect",
    ),
    (
        "embedding-profile",
        "ai",
        "Document and query embeddings share a versioned compatible retrieval profile",
        "embedding profile",
        "keep search vectors compatible",
    ),
    (
        "summary-cache",
        "ai",
        "Summary cache keys include provider model prompt version and source range",
        "summary cache",
        "when an AI recap can be reused",
    ),
    (
        "owner-lock",
        "database",
        "Membership rows are locked while owner-only room mutations commit",
        "membership lock",
        "prevent concurrent owner changes",
    ),
    (
        "read-receipt",
        "realtime",
        "Read positions only move forward within the same room",
        "read receipt",
        "track the last message someone viewed",
    ),
    (
        "ai-privacy",
        "privacy",
        "AI stays disabled by default and historical backfill requires explicit owner action",
        "AI privacy",
        "avoid silently sending old chats externally",
    ),
)


def build_messages() -> list[EvalMessage]:
    messages: list[EvalMessage] = []
    sequence = 0
    for topic, room, anchor, keyword, paraphrase in TOPICS:
        variants = (
            anchor,
            f"Decision recorded for {topic}: {paraphrase}.",
            f"Follow-up owner will verify the {keyword} behavior.",
            f"Unrelated status: the design review for {room} is scheduled.",
            "The team discussed colors, spacing, and documentation wording.",
            "A recent message mentions an index card in the user interface, not a database index.",
            f"Question remains about monitoring for the {topic} workflow.",
            "No production deployment was authorized during this conversation.",
            "The meeting ended with no changes to unrelated features.",
            "Recent noise: lunch plans and calendar availability were discussed.",
        )
        for offset, text in enumerate(variants):
            sequence += 1
            messages.append(
                EvalMessage(
                    id=f"m-{topic}-{offset + 1:02d}",
                    room=room,
                    text=text,
                    topic=topic,
                    sequence=sequence,
                )
            )
    return messages


def build_queries() -> list[EvalQuery]:
    queries: list[EvalQuery] = []
    for topic, _room, _anchor, keyword, paraphrase in TOPICS:
        relevance = {
            f"m-{topic}-01": 3,
            f"m-{topic}-02": 2,
            f"m-{topic}-03": 1,
        }
        queries.extend(
            (
                EvalQuery(f"q-{topic}-exact", keyword, relevance, "exact"),
                EvalQuery(f"q-{topic}-paraphrase", paraphrase, relevance, "paraphrase"),
                EvalQuery(
                    f"q-{topic}-question",
                    f"What was decided about {paraphrase}?",
                    relevance,
                    "question",
                ),
                EvalQuery(f"q-{topic}-ambiguous", topic.replace("-", " "), relevance, "ambiguous"),
            )
        )
    negative_texts = (
        "GPU training checkpoint",
        "mobile push notification vendor",
        "video transcoding pipeline",
        "cryptocurrency payment gateway",
        "facial recognition model",
        "Kubernetes autoscaling policy",
        "voice call recording",
        "advertising attribution pixel",
        "warehouse inventory barcode",
        "medical diagnosis classifier",
        "satellite image segmentation",
        "customer billing invoice",
    )
    queries.extend(
        EvalQuery(f"q-negative-{index:02d}", text, {}, "negative")
        for index, text in enumerate(negative_texts, start=1)
    )
    return queries


MESSAGES = build_messages()
QUERIES = build_queries()

assert len(MESSAGES) == 120
assert len(QUERIES) == 60
