"""
app/models/folder.py
────────────────────
Folder model — groups related chats (e.g., by patient or case type).

Key design decisions:
- Each folder has its own `auth_level` controlling step-up authentication.
- `is_mini_folder` = True means this folder was auto-created from a chat continuation.
- `parent_chat_id` links a mini-folder back to the chat that spawned it.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.database import Base


class FolderAuthLevel(str, enum.Enum):
    STANDARD = "standard"       # Login is sufficient
    STEP_UP = "step_up"         # Re-authentication required (MFA prompt)
    HIGH_SECURITY = "high_security"  # Full re-auth + IP restriction


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # hex color

    # Auth & security
    auth_level: Mapped[FolderAuthLevel] = mapped_column(
        SAEnum(FolderAuthLevel), default=FolderAuthLevel.STANDARD
    )
    zero_retention_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    # If True, messages in this folder are never persisted to PostgreSQL.
    # They live in Redis with a TTL and disappear when the session ends.

    # Mini-folder (chat continuation) tracking
    is_mini_folder: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
    )
    depth: Mapped[int] = mapped_column(Integer, default=0)
    # depth=0 is a top-level folder; depth>0 is a nested mini-folder

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="folders")
    chats: Mapped[list["Chat"]] = relationship(
        "Chat",
        back_populates="folder",
        foreign_keys="Chat.folder_id",
        cascade="all, delete-orphan",
    )
    shares: Mapped[list["Share"]] = relationship(
        "Share", back_populates="folder", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        kind = "MiniFolder" if self.is_mini_folder else "Folder"
        return f"<{kind} '{self.name}' (auth={self.auth_level})>"
