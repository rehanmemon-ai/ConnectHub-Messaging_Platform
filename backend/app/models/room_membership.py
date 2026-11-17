import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.user import User


class RoomMembership(Base):
    __tablename__ = "room_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_room_memberships_user_id_users", ondelete="RESTRICT"),
        primary_key=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", name="fk_room_memberships_room_id_rooms", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "messages.id",
            name="fk_room_memberships_last_read_message_id_messages",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="memberships")
    room: Mapped["Room"] = relationship(back_populates="memberships")

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'member')", name="valid_role"),
        Index("ix_room_memberships_room_user", "room_id", "user_id"),
        Index("ix_room_memberships_user_joined_room", "user_id", joined_at.desc(), room_id.desc()),
        Index("ix_room_memberships_last_read_message_id", "last_read_message_id"),
        Index(
            "uq_room_memberships_one_owner_per_room",
            "room_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )
