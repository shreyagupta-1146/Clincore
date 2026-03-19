"""app/schemas/message.py"""
import uuid
from datetime import datetime
from pydantic import BaseModel

from app.schemas.ai import AIResponse


class MessageCreate(BaseModel):
    content: str
    image_base64: str | None = None  # base64 encoded image
    image_mime_type: str | None = None  # "image/jpeg", "image/png"


class SendMessageRequest(MessageCreate):
    """Used in POST /chats/{chat_id}/messages"""
    pass


class MessageRead(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    role: str
    content: str  # decrypted content returned to frontend
    image_url: str | None = None  # signed URL (not raw path)
    ai_metadata: dict | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class SendMessageResponse(BaseModel):
    """Full response from POST /chats/{chat_id}/messages"""
    user_message: MessageRead
    ai_message: MessageRead
    ai_response: AIResponse
    chat_near_limit: bool = False  # True when approaching MAX_MESSAGES_PER_CHAT
    suggest_continuation: bool = False
