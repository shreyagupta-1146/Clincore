"""
app/models/message.py
─────────────────────
Message model — individual messages in a chat.

Security design:
- `content_encrypted`: the message text stored as AES-256 encrypted bytea.
  We encrypt/decrypt at the application layer using the DB_ENCRYPTION_KEY.
  This means even a raw database dump cannot be read without the key.
- `image_path`: the MinIO object path (not a public URL — images are served
  through a signed URL endpoint that requires authentication).
- `redacted_content`: the PII-stripped version sent to the LLM API.
  We store this separately so auditors can confirm what was sent externally.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, LargeBinary, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
    )

    # "user" (doctor's input) or "assistant" (AI response)
    role: Mapped[str] = mapped_column(String(16))

    # ── Encrypted storage ────────────────────────────────────────────────────
    # Stored as AES-256 encrypted bytes via pgcrypto.
    # Python side: use app.core.encryption to encrypt before insert,
    # decrypt after select.
    content_encrypted: Mapped[bytes] = mapped_column(LargeBinary)

    # ── Image attachment ─────────────────────────────────────────────────────
    # MinIO object path, e.g. "clinicore-images/chat_id/image_uuid.jpg"
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── PII audit ────────────────────────────────────────────────────────────
    # What was actually sent to the external LLM API (PII redacted)
    redacted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    pii_entities_found: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # e.g. [{"type": "PERSON", "score": 0.95, "start": 10, "end": 18}]

    # ── AI response metadata ──────────────────────────────────────────────────
    # Stored as JSON — the structured response from the LLM
    # Includes: reasoning_steps, differentials, missing_info, red_flags, etc.
    ai_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Which LLM model was used (for reproducibility / audit)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Was this message processed in zero-retention mode?
    zero_retention: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    # Relationship
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message role={self.role} chat={self.chat_id}>"
