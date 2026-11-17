import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.room_membership import RoomMembership


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", server_default=""
    )
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="public", server_default="public"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["RoomMembership"]] = relationship(
        back_populates="room", passive_deletes=True
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="room", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint("name = btrim(name)", name="name_trimmed"),
        CheckConstraint("description = btrim(description)", name="description_trimmed"),
        CheckConstraint("visibility IN ('public', 'private')", name="valid_visibility"),
        Index("ix_rooms_discovery", created_at.desc(), id.desc()),
        Index(
            "ix_rooms_public_discovery",
            created_at.desc(),
            id.desc(),
            postgresql_where=text("visibility = 'public'"),
        ),
    )
