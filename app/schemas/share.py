"""app/schemas/share.py"""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class ShareCreate(BaseModel):
    folder_id: uuid.UUID
    recipient_name: str
    recipient_role: str  # e.g., "Dermatologist", "Radiologist"
    recipient_email: EmailStr | None = None
    recipient_institution: str | None = None
    can_view_messages: bool = True
    can_view_images: bool = True
    can_add_comments: bool = False
    can_reshare: bool = False
    message: str | None = None  # reason for sharing
    expires_hours: int | None = 72  # link expiry; None = no expiry


class ShareAccept(BaseModel):
    """Recipient calls this with their auth token to accept the share."""
    access_token: str


class ShareRead(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    recipient_name: str
    recipient_role: str
    recipient_email: str | None
    can_view_messages: bool
    can_view_images: bool
    can_add_comments: bool
    is_accepted: bool
    accepted_at: datetime | None
    is_revoked: bool
    expires_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
