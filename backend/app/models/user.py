import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.message import Message
    from app.models.room_membership import RoomMembership


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    memberships: Mapped[list["RoomMembership"]] = relationship(
        back_populates="user", passive_deletes=True
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="sender", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("char_length(btrim(username)) BETWEEN 1 AND 50", name="username_length"),
        CheckConstraint("username = btrim(username)", name="username_trimmed"),
        CheckConstraint("char_length(btrim(email)) BETWEEN 3 AND 320", name="email_length"),
        CheckConstraint("email = btrim(email)", name="email_trimmed"),
        CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 1 AND 100", name="display_name_length"
        ),
        CheckConstraint("display_name = btrim(display_name)", name="display_name_trimmed"),
        Index("uq_users_username_ci", func.lower(username), unique=True),
        Index("uq_users_email_ci", func.lower(email), unique=True),
    )
