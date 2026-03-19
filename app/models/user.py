"""
app/models/user.py
──────────────────
User model — represents a medical professional.
Auth0 manages authentication; we store the Auth0 sub ID as the link.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    SPECIALIST = "specialist"
    RESEARCHER = "researcher"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    auth0_sub: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(256))
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.DOCTOR
    )
    institution: Mapped[str | None] = mapped_column(String(256), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    folders: Mapped[list["Folder"]] = relationship(
        "Folder", back_populates="owner", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
