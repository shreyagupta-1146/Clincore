"""
app/models/audit.py
───────────────────
Immutable audit log — every significant action is recorded here.

HIPAA requires audit trails showing: who accessed what, when, and from where.
This table is append-only — no updates or deletes are permitted in application
code. Retention policy enforced by a scheduled cleanup task that removes entries
older than AUDIT_LOG_RETENTION_DAYS (default 7 years for HIPAA compliance).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action taxonomy:
    # AUTH: login, logout, mfa_success, mfa_fail, stepup_success, stepup_fail
    # FOLDER: folder_create, folder_open, folder_archive, folder_delete
    # CHAT: chat_create, chat_open, chat_continue, chat_archive
    # MESSAGE: message_send, message_view
    # IMAGE: image_upload, image_view, image_delete
    # SHARE: share_create, share_accept, share_revoke, share_access
    # AI: ai_query, ai_response_generated
    # KNOWLEDGE: knowledge_update_triggered
    action: Mapped[str] = mapped_column(String(64), index=True)

    # Resource that was acted upon
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # e.g., "folder", "chat", "message", "share"
    resource_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # The UUID of the resource as a string

    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Additional structured context (flexible JSON)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # e.g., {"model": "claude-3", "pii_redacted": true, "entities_found": 3}

    # Notes for compliance reviewers
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    # Relationship
    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user={self.user_id} at {self.timestamp}>"
