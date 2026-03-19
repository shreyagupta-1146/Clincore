"""
app/models/share.py
───────────────────
Secure sharing model.

Flow:
1. Sender creates a Share record with recipient name + role (+ optional email).
2. System sends recipient a link with a unique token.
3. Recipient must authenticate (login + MFA) before access is granted.
4. ShareAudit tracks every time the share is accessed.

This implements a "chain of custody" model for clinical information.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Share(Base):
    __tablename__ = "shares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("folders.id", ondelete="CASCADE"), index=True
    )
    shared_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )

    # ── Recipient Details (must be specified before sharing) ──────────────────
    recipient_name: Mapped[str] = mapped_column(String(256))
    recipient_role: Mapped[str] = mapped_column(String(128))
    recipient_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recipient_institution: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # ── Access Control ────────────────────────────────────────────────────────
    # Unique token sent to recipient — must be presented alongside auth
    access_token: Mapped[str] = mapped_column(String(256), unique=True, index=True)

    # Permissions granted
    can_view_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    can_view_images: Mapped[bool] = mapped_column(Boolean, default=True)
    can_add_comments: Mapped[bool] = mapped_column(Boolean, default=False)
    can_reshare: Mapped[bool] = mapped_column(Boolean, default=False)

    # Expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Share message / reason (e.g., "Consult on dermatology findings")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status tracking
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    folder: Mapped["Folder"] = relationship("Folder", back_populates="shares")
    access_logs: Mapped[list["ShareAudit"]] = relationship(
        "ShareAudit", back_populates="share", cascade="all, delete-orphan"
    )


class ShareAudit(Base):
    """
    Every access to a shared folder is logged here.
    Provides the audit trail for shared clinical data.
    """
    __tablename__ = "share_audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    share_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shares.id", ondelete="CASCADE"), index=True
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    auth_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # e.g., "mfa_totp", "mfa_email", "password_only"

    # What actions were taken in this session
    actions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    share: Mapped["Share"] = relationship("Share", back_populates="access_logs")
