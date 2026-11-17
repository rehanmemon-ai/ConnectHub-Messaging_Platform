"""Create the five-entity ConnectHub schema.

Revision ID: 20261116_0001
Revises: None
Create Date: 2026-11-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261116_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 100",
            name=op.f("ck_users_display_name_length"),
        ),
        sa.CheckConstraint(
            "display_name = btrim(display_name)", name=op.f("ck_users_display_name_trimmed")
        ),
        sa.CheckConstraint(
            "char_length(btrim(email)) BETWEEN 3 AND 320", name=op.f("ck_users_email_length")
        ),
        sa.CheckConstraint("email = btrim(email)", name=op.f("ck_users_email_trimmed")),
        sa.CheckConstraint(
            "char_length(btrim(username)) BETWEEN 1 AND 50",
            name=op.f("ck_users_username_length"),
        ),
        sa.CheckConstraint("username = btrim(username)", name=op.f("ck_users_username_trimmed")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("uq_users_email_ci", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_users_username_ci", "users", [sa.text("lower(username)")], unique=True)

    op.create_table(
        "rooms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), server_default="", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "description = btrim(description)", name=op.f("ck_rooms_description_trimmed")
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 100", name=op.f("ck_rooms_name_length")
        ),
        sa.CheckConstraint("name = btrim(name)", name=op.f("ck_rooms_name_trimmed")),
        sa.PrimaryKeyConstraint("id", name="pk_rooms"),
    )
    op.create_index(
        "ix_rooms_discovery", "rooms", [sa.text("created_at DESC"), sa.text("id DESC")], unique=False
    )

    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_auth_sessions_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_auth_sessions_token_hash_sha256_hex"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)

    op.create_table(
        "room_memberships",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'member')", name=op.f("ck_room_memberships_valid_role")
        ),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name="fk_room_memberships_room_id_rooms", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_room_memberships_user_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("user_id", "room_id", name="pk_room_memberships"),
    )
    op.create_index(
        "ix_room_memberships_room_user", "room_memberships", ["room_id", "user_id"], unique=False
    )
    op.create_index(
        "ix_room_memberships_user_joined_room",
        "room_memberships",
        ["user_id", sa.text("joined_at DESC"), sa.text("room_id DESC")],
        unique=False,
    )
    op.create_index(
        "uq_room_memberships_one_owner_per_room",
        "room_memberships",
        ["room_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )

    op.create_table(
        "messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.String(length=4000), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(btrim(content)) BETWEEN 1 AND 4000",
            name=op.f("ck_messages_content_length"),
        ),
        sa.CheckConstraint("content = btrim(content)", name=op.f("ck_messages_content_trimmed")),
        sa.ForeignKeyConstraint(
            ["room_id"], ["rooms.id"], name="fk_messages_room_id_rooms", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"], ["users.id"], name="fk_messages_sender_id_users", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
    )
    op.create_index(
        "ix_messages_room_history",
        "messages",
        ["room_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_messages_room_history", table_name="messages")
    op.drop_table("messages")
    op.drop_index("uq_room_memberships_one_owner_per_room", table_name="room_memberships")
    op.drop_index("ix_room_memberships_user_joined_room", table_name="room_memberships")
    op.drop_index("ix_room_memberships_room_user", table_name="room_memberships")
    op.drop_table("room_memberships")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_rooms_discovery", table_name="rooms")
    op.drop_table("rooms")
    op.drop_index("uq_users_username_ci", table_name="users")
    op.drop_index("uq_users_email_ci", table_name="users")
    op.drop_table("users")

