"""Add complete backend messaging and advanced feature state.

Revision ID: 20261116_0002
Revises: 20261116_0001
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261116_0002"
down_revision: str | None = "20261116_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "rooms",
        sa.Column("visibility", sa.String(length=16), server_default="public", nullable=False),
    )
    op.create_check_constraint(
        "ck_rooms_valid_visibility", "rooms", "visibility IN ('public', 'private')"
    )
    op.create_index(
        "ix_rooms_public_discovery",
        "rooms",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
        postgresql_where=sa.text("visibility = 'public'"),
    )

    op.add_column(
        "messages",
        sa.Column("client_idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "uq_messages_sender_room_idempotency",
        "messages",
        ["sender_id", "room_id", "client_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("client_idempotency_key IS NOT NULL"),
    )

    op.add_column(
        "room_memberships",
        sa.Column("last_read_message_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "room_memberships",
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_room_memberships_last_read_message_id_messages",
        "room_memberships",
        "messages",
        ["last_read_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_room_memberships_last_read_message_id",
        "room_memberships",
        ["last_read_message_id"],
        unique=False,
    )

    op.create_table(
        "room_invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inviter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invitee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("inviter_id <> invitee_id", name="ck_room_invitations_different_users"),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_room_invitations_expiry_after_creation"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'revoked', 'expired')",
            name="ck_room_invitations_valid_status",
        ),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_room_invitations"),
    )
    op.create_index(
        "ix_room_invitations_invitee_status_created",
        "room_invitations",
        ["invitee_id", "status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_room_invitations_room_status", "room_invitations", ["room_id", "status"]
    )
    op.create_index(
        "uq_room_invitations_pending_invitee",
        "room_invitations",
        ["room_id", "invitee_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invitation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dedup_key", sa.String(length=160), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invitation_id"], ["room_invitations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.UniqueConstraint("dedup_key", name="uq_notifications_dedup_key"),
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    op.create_table(
        "ai_summaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_start_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_end_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_message_count", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_ai_summaries"),
        sa.UniqueConstraint(
            "room_id", "provider", "model", "source_fingerprint", name="uq_ai_summaries_room_provider_model_source_fingerprint"
        ),
    )
    op.create_index(
        "ix_ai_summaries_room_created",
        "ai_summaries",
        ["room_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "message_embeddings",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("dimensions BETWEEN 1 AND 3072", name="ck_message_embeddings_valid_dimensions"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", name="pk_message_embeddings"),
    )

    op.create_table(
        "embedding_jobs",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_embedding_jobs_nonnegative_attempts"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_embedding_jobs_valid_status",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("message_id", name="pk_embedding_jobs"),
    )
    op.create_index(
        "ix_embedding_jobs_claim",
        "embedding_jobs",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_embedding_jobs_claim", table_name="embedding_jobs")
    op.drop_table("embedding_jobs")
    op.drop_table("message_embeddings")
    op.drop_index("ix_ai_summaries_room_created", table_name="ai_summaries")
    op.drop_table("ai_summaries")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("uq_room_invitations_pending_invitee", table_name="room_invitations")
    op.drop_index("ix_room_invitations_room_status", table_name="room_invitations")
    op.drop_index("ix_room_invitations_invitee_status_created", table_name="room_invitations")
    op.drop_table("room_invitations")
    op.drop_index("ix_room_memberships_last_read_message_id", table_name="room_memberships")
    op.drop_constraint(
        "fk_room_memberships_last_read_message_id_messages",
        "room_memberships",
        type_="foreignkey",
    )
    op.drop_column("room_memberships", "last_read_at")
    op.drop_column("room_memberships", "last_read_message_id")
    op.drop_index("uq_messages_sender_room_idempotency", table_name="messages")
    op.drop_column("messages", "client_idempotency_key")
    op.drop_index("ix_rooms_public_discovery", table_name="rooms")
    op.drop_constraint("ck_rooms_valid_visibility", "rooms", type_="check")
    op.drop_column("rooms", "visibility")
    op.drop_column("users", "last_seen_at")
