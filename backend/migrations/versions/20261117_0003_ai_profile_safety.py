"""Add AI profile isolation and versioned summary metadata.

Revision ID: 20261117_0003
Revises: 20261116_0002
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261117_0003"
down_revision: str | None = "20261116_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_EMBEDDING_PROFILE = "legacy:unprofiled"
LEGACY_SUMMARY_PROMPT = "legacy-summary-v0"


def upgrade() -> None:
    op.add_column(
        "message_embeddings",
        sa.Column("profile", sa.String(length=255), nullable=True),
    )
    op.execute(
        sa.text("UPDATE message_embeddings SET profile = :profile WHERE profile IS NULL").bindparams(
            profile=LEGACY_EMBEDDING_PROFILE
        )
    )
    op.alter_column("message_embeddings", "profile", nullable=False)

    op.add_column("embedding_jobs", sa.Column("profile", sa.String(length=255), nullable=True))
    op.add_column("embedding_jobs", sa.Column("origin", sa.String(length=16), nullable=True))
    op.execute(
        sa.text(
            "UPDATE embedding_jobs SET profile = :profile, origin = 'legacy' "
            "WHERE profile IS NULL OR origin IS NULL"
        ).bindparams(profile=LEGACY_EMBEDDING_PROFILE)
    )
    op.alter_column("embedding_jobs", "profile", nullable=False)
    op.alter_column("embedding_jobs", "origin", nullable=False)
    op.create_check_constraint(
        "ck_embedding_jobs_valid_origin",
        "embedding_jobs",
        "origin IN ('automatic', 'backfill', 'legacy')",
    )
    op.drop_index("ix_embedding_jobs_claim", table_name="embedding_jobs")
    op.create_index(
        "ix_embedding_jobs_claim",
        "embedding_jobs",
        ["profile", "status", "next_attempt_at", "created_at"],
    )

    op.add_column(
        "ai_summaries", sa.Column("prompt_version", sa.String(length=128), nullable=True)
    )
    op.add_column("ai_summaries", sa.Column("source_truncated", sa.Boolean(), nullable=True))
    op.add_column("ai_summaries", sa.Column("input_characters", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE ai_summaries SET prompt_version = :prompt, source_truncated = false, "
            "input_characters = 0 WHERE prompt_version IS NULL"
        ).bindparams(prompt=LEGACY_SUMMARY_PROMPT)
    )
    op.alter_column("ai_summaries", "prompt_version", nullable=False)
    op.alter_column("ai_summaries", "source_truncated", nullable=False)
    op.alter_column("ai_summaries", "input_characters", nullable=False)
    op.drop_constraint(
        "uq_ai_summaries_room_provider_model_source_fingerprint",
        "ai_summaries",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_ai_summaries_room_profile_source_fingerprint",
        "ai_summaries",
        ["room_id", "provider", "model", "prompt_version", "source_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ai_summaries_room_profile_source_fingerprint", "ai_summaries", type_="unique"
    )
    op.create_unique_constraint(
        "uq_ai_summaries_room_provider_model_source_fingerprint",
        "ai_summaries",
        ["room_id", "provider", "model", "source_fingerprint"],
    )
    op.drop_column("ai_summaries", "input_characters")
    op.drop_column("ai_summaries", "source_truncated")
    op.drop_column("ai_summaries", "prompt_version")

    op.drop_index("ix_embedding_jobs_claim", table_name="embedding_jobs")
    op.create_index(
        "ix_embedding_jobs_claim",
        "embedding_jobs",
        ["status", "next_attempt_at", "created_at"],
    )
    op.drop_constraint("ck_embedding_jobs_valid_origin", "embedding_jobs", type_="check")
    op.drop_column("embedding_jobs", "origin")
    op.drop_column("embedding_jobs", "profile")
    op.drop_column("message_embeddings", "profile")
