"""app/schemas/chat.py"""
import uuid
from datetime import datetime
from pydantic import BaseModel


class ChatCreate(BaseModel):
    folder_id: uuid.UUID
    title: str | None = None  # auto-generated if not provided


class ContinueChatRequest(BaseModel):
    """Request to create a mini-folder continuation of this chat."""
    mini_folder_name: str | None = None  # defaults to "{original title} — Continued"
    continuation_reason: str | None = None  # e.g., "Expanding on abnormal labs"


class ChatRead(BaseModel):
    id: uuid.UUID
    folder_id: uuid.UUID
    title: str
    summary: str | None
    message_count: int
    is_mini_folder_root: bool
    continued_from_chat_id: uuid.UUID | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
