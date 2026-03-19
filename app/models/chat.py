"""
app/models/chat.py
──────────────────
Chat model — a single focused conversation thread within a folder.

Design: Each chat is intentionally kept small (MAX_MESSAGES_PER_CHAT limit).
When a doctor needs to expand on a topic, they use "Continue Chat" which
creates a mini-folder with a new chat linked to this one.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        index=True,
    )

    # Title is auto-generated from the first message by the LLM
    title: Mapped[str] = mapped_column(String(256), default="New Chat")
    # AI-generated summary updated when chat approaches message limit
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    message_count: Mapped[int] = mapped_column(Integer, default=0)
    is_mini_folder_root: Mapped[bool] = mapped_column(Boolean, default=False)
    # True if this chat is the "root" chat of a mini-folder

    # Continuation chain: which chat did this one branch from?
    continued_from_chat_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    folder: Mapped["Folder"] = relationship(
        "Folder", back_populates="chats", foreign_keys=[folder_id]
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    continued_from: Mapped["Chat | None"] = relationship(
        "Chat", remote_side="Chat.id", foreign_keys=[continued_from_chat_id]
    )

    def __repr__(self) -> str:
        return f"<Chat '{self.title}' ({self.message_count} msgs)>"
