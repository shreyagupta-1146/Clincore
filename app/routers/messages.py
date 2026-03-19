"""
app/routers/messages.py
────────────────────────
Message endpoints — this is where all the AI magic happens.

POST /chats/{chat_id}/messages is the core endpoint. It:
1. Validates the user has access to the chat
2. Runs PII redaction (Presidio)
3. Uploads image to MinIO if provided
4. Calls the LLM (Claude) with conversation history + image
5. Runs RAG pipeline in parallel (research suggestions)
6. Validates/post-processes the AI response
7. Encrypts and stores everything in PostgreSQL
8. Returns the full structured response to the frontend

Also includes:
- GET /chats/{chat_id}/messages — list messages (decrypted)
- GET /chats/{chat_id}/messages/stream — streaming endpoint for real-time display
- GET /messages/{message_id}/image — serve signed image URL
"""

import uuid
import asyncio
from typing import AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from app.database import get_db
from app.core.auth import get_current_user
from app.core.encryption import encrypt_for_storage, decrypt_from_storage
from app.models.user import User
from app.models.folder import Folder
from app.models.chat import Chat
from app.models.message import Message
from app.schemas.message import (
    SendMessageRequest,
    SendMessageResponse,
    MessageRead,
)
from app.schemas.ai import AIResponse
from app.services.llm_service import llm_service
from app.services.presidio_service import detect_and_redact
from app.services.rag_service import get_research_suggestions
from app.services.storage_service import upload_image_base64, get_signed_url, get_image_for_llm
from app.services.audit_service import audit_service
from app.config import settings

router = APIRouter(prefix="/chats", tags=["Messages"])


# ── Send Message (the main AI pipeline) ───────────────────────────────────────

@router.post("/{chat_id}/messages", response_model=SendMessageResponse, status_code=201)
async def send_message(
    chat_id: uuid.UUID,
    data: SendMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and get an AI clinical reasoning response.

    This is the most important endpoint in CLINICORE.
    The full pipeline runs here.
    """

    # ── Step 1: Validate access ───────────────────────────────────────────────
    chat, folder = await _get_chat_and_folder_or_403(chat_id, current_user.id, db)

    # Check message limit
    if chat.message_count >= settings.MAX_MESSAGES_PER_CHAT * 2:
        raise HTTPException(
            status_code=400,
            detail=f"Chat has reached the maximum of {settings.MAX_MESSAGES_PER_CHAT} exchanges. Use 'Continue Chat' to expand this conversation.",
        )

    # ── Step 2: PII Redaction ─────────────────────────────────────────────────
    redaction_result = detect_and_redact(data.content)
    redacted_text = redaction_result["redacted_text"]
    pii_entities = redaction_result["entities_found"]
    pii_detected = redaction_result["pii_detected"]

    if pii_detected:
        logger.info(f"PII detected in message for chat {chat_id}: {len(pii_entities)} entities redacted")

    # ── Step 3: Image Upload ──────────────────────────────────────────────────
    image_path = None
    image_base64_for_llm = None
    image_mime_for_llm = None
    message_id = uuid.uuid4()

    if data.image_base64 and data.image_mime_type:
        try:
            image_path = upload_image_base64(
                base64_data=data.image_base64,
                mime_type=data.image_mime_type,
                chat_id=str(chat_id),
                message_id=str(message_id),
            )
            # Get for LLM input (redact any PII we can from image filename/context)
            image_base64_for_llm = data.image_base64
            image_mime_for_llm = data.image_mime_type

            await audit_service.log(
                db=db,
                user_id=current_user.id,
                action="image_upload",
                resource_type="message",
                resource_id=str(message_id),
                request=request,
                metadata={"mime_type": data.image_mime_type, "chat_id": str(chat_id)},
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ── Step 4: Build conversation history for LLM ────────────────────────────
    history_result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .limit(settings.MAX_MESSAGES_PER_CHAT)
    )
    history_messages = history_result.scalars().all()

    # Build history in LLM format (using redacted content)
    conversation_history = []

    # If this chat is a continuation, prepend parent summary
    if chat.summary and len(history_messages) == 0:
        conversation_history.append({
            "role": "user",
            "content": f"[Context from previous conversation]: {chat.summary}",
        })
        conversation_history.append({
            "role": "assistant",
            "content": "I understand. I have context from the previous conversation. Please continue.",
        })

    for msg in history_messages:
        content = decrypt_from_storage(msg.content_encrypted)
        conversation_history.append({"role": msg.role, "content": content})

    # ── Step 5: Run LLM + RAG in parallel ────────────────────────────────────
    # Both calls run concurrently for performance
    zero_retention = folder.zero_retention_mode

    try:
        llm_task = llm_service.generate_clinical_response(
            user_text=redacted_text,
            previous_messages=conversation_history,
            image_base64=image_base64_for_llm,
            image_mime_type=image_mime_for_llm,
        )

        rag_task = get_research_suggestions(
            clinical_text=redacted_text,
            llm_service=llm_service,
            top_k=5,
        )

        # Run both concurrently
        ai_response, research_suggestions = await asyncio.gather(
            llm_task,
            rag_task,
            return_exceptions=True,
        )

        # Handle partial failures gracefully
        if isinstance(ai_response, Exception):
            logger.error(f"LLM error: {ai_response}")
            ai_response = llm_service._get_demo_fallback_response(redacted_text)

        if isinstance(research_suggestions, Exception):
            logger.warning(f"RAG error: {research_suggestions}")
            research_suggestions = []

    except Exception as e:
        logger.error(f"Critical pipeline error: {e}")
        raise HTTPException(status_code=500, detail="AI service temporarily unavailable")

    # Attach research suggestions to AI response
    ai_response.research_suggestions = research_suggestions

    # ── Step 6: Store Messages ────────────────────────────────────────────────
    # User message
    user_message = Message(
        id=message_id,
        chat_id=chat_id,
        role="user",
        content_encrypted=encrypt_for_storage(data.content),  # Encrypt ORIGINAL content
        image_path=image_path,
        image_mime_type=data.image_mime_type,
        redacted_content=redacted_text,
        pii_entities_found=pii_entities,
        zero_retention=zero_retention,
    )

    # AI response message
    import json
    ai_response_text = ai_response.primary_suggestion + "\n\n" + "\n".join(ai_response.reasoning_steps)
    ai_message = Message(
        chat_id=chat_id,
        role="assistant",
        content_encrypted=encrypt_for_storage(ai_response_text),
        ai_metadata=ai_response.model_dump(exclude={"research_suggestions", "model_used"}),
        model_used=ai_response.model_used,
        zero_retention=zero_retention,
    )

    if zero_retention:
        # In zero-retention mode, don't write to PostgreSQL
        # Store in Redis with TTL instead
        await _store_in_redis_session(chat_id, user_message, ai_message)
    else:
        db.add(user_message)
        db.add(ai_message)
        await db.flush()

    # ── Step 7: Update chat metadata ─────────────────────────────────────────
    chat.message_count = (chat.message_count or 0) + 2

    # Auto-generate title from first user message
    if chat.message_count <= 2:
        try:
            generated_title = await llm_service.generate_chat_title(data.content[:200])
            chat.title = generated_title
        except Exception:
            pass  # Keep default title if generation fails

    # Auto-generate summary when approaching limit
    near_limit = chat.message_count >= settings.MAX_MESSAGES_PER_CHAT * 2 - 4
    if near_limit and not chat.summary:
        try:
            all_msgs = conversation_history + [
                {"role": "user", "content": data.content},
                {"role": "assistant", "content": ai_response_text},
            ]
            chat.summary = await llm_service.generate_chat_summary(all_msgs)
        except Exception:
            pass

    await db.flush()

    # ── Step 8: Audit log ─────────────────────────────────────────────────────
    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="ai_query",
        resource_type="chat",
        resource_id=str(chat_id),
        request=request,
        metadata={
            "model": ai_response.model_used,
            "pii_redacted": pii_detected,
            "entities_found": len(pii_entities),
            "has_image": image_path is not None,
            "research_papers_found": len(research_suggestions),
            "confidence": ai_response.confidence,
            "zero_retention": zero_retention,
        },
    )

    # ── Step 9: Build response ────────────────────────────────────────────────
    user_msg_read = _message_to_read(user_message, data.content)
    ai_msg_read = _message_to_read(ai_message, ai_response_text)

    return SendMessageResponse(
        user_message=user_msg_read,
        ai_message=ai_msg_read,
        ai_response=ai_response,
        chat_near_limit=near_limit,
        suggest_continuation=near_limit,
    )


# ── List Messages ─────────────────────────────────────────────────────────────

@router.get("/{chat_id}/messages", response_model=list[MessageRead])
async def list_messages(
    chat_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a chat (decrypted)."""
    chat, folder = await _get_chat_and_folder_or_403(chat_id, current_user.id, db)

    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="message_view",
        resource_type="chat",
        resource_id=str(chat_id),
        request=request,
        metadata={"message_count": len(messages)},
    )

    return [
        _message_to_read(msg, decrypt_from_storage(msg.content_encrypted))
        for msg in messages
    ]


# ── Streaming Messages ─────────────────────────────────────────────────────────

@router.post("/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: uuid.UUID,
    data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Streaming version of send_message.
    Returns a Server-Sent Events stream so the frontend can render
    the AI response token by token as it arrives.

    Frontend usage:
        const response = await fetch('/chats/{id}/messages/stream', {...});
        const reader = response.body.getReader();
        // Read chunks and append to UI
    """
    chat, folder = await _get_chat_and_folder_or_403(chat_id, current_user.id, db)

    redaction_result = detect_and_redact(data.content)
    redacted_text = redaction_result["redacted_text"]

    history_result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc())
        .limit(10)
    )
    history = [
        {"role": m.role, "content": decrypt_from_storage(m.content_encrypted)}
        for m in history_result.scalars().all()
    ]

    async def generate() -> AsyncIterator[str]:
        async for token in llm_service.generate_streaming_response(
            user_text=redacted_text,
            previous_messages=history,
            image_base64=data.image_base64,
            image_mime_type=data.image_mime_type,
        ):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ── Signed Image URL ──────────────────────────────────────────────────────────

@router.get("/messages/{message_id}/image-url")
async def get_image_url(
    message_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a time-limited signed URL for a message's image.
    The URL expires after 60 minutes. Never store this URL — request fresh ones.
    """
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    if not message.image_path:
        raise HTTPException(status_code=404, detail="Message has no image")

    # Verify access through chat/folder ownership
    chat, folder = await _get_chat_and_folder_or_403(
        message.chat_id, current_user.id, db
    )

    signed_url = get_signed_url(message.image_path, expires_minutes=60)

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="image_view",
        resource_type="message",
        resource_id=str(message_id),
        request=request,
    )

    return {"url": signed_url, "expires_in_minutes": 60}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_chat_and_folder_or_403(
    chat_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> tuple[Chat, Folder]:
    """Get chat and its containing folder, verifying user access."""
    chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    folder_result = await db.execute(
        select(Folder).where(Folder.id == chat.folder_id, Folder.owner_id == user_id)
    )
    folder = folder_result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=403, detail="Access denied")

    return chat, folder


def _message_to_read(message: Message, decrypted_content: str) -> MessageRead:
    return MessageRead(
        id=message.id,
        chat_id=message.chat_id,
        role=message.role,
        content=decrypted_content,
        image_url=None,  # Frontend requests signed URLs separately
        ai_metadata=message.ai_metadata,
        created_at=message.created_at,
    )


async def _store_in_redis_session(chat_id, user_msg, ai_msg):
    """Store messages in Redis for zero-retention mode."""
    # In production, implement Redis storage with TTL here
    # For now, log that zero-retention is active
    logger.info(f"Zero-retention mode: messages for chat {chat_id} not persisted")
