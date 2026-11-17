from app import models  # noqa: F401
from app.db.base import Base


def test_metadata_preserves_core_tables_and_contains_approved_extensions() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "auth_sessions",
        "rooms",
        "room_memberships",
        "messages",
        "room_invitations",
        "notifications",
        "ai_summaries",
        "message_embeddings",
        "embedding_jobs",
    }
