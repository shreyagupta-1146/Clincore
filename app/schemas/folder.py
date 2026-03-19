"""app/schemas/folder.py"""
import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.folder import FolderAuthLevel


class FolderCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None
    auth_level: FolderAuthLevel = FolderAuthLevel.STANDARD
    zero_retention_mode: bool = False


class FolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    auth_level: FolderAuthLevel | None = None


class FolderRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    color: str | None
    auth_level: FolderAuthLevel
    zero_retention_mode: bool
    is_mini_folder: bool
    parent_chat_id: uuid.UUID | None
    depth: int
    is_archived: bool
    chat_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}
