"""
app/routers/chats.py
─────────────────────
Chat management endpoints.

Key feature: "Chat Continuation" → creates a mini-folder.
When a chat approaches MAX_MESSAGES_PER_CHAT, the user is nudged
to continue in a linked mini-folder rather than a single long thread.
This keeps chats focused and data management efficient.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.folder import Folder
from app.models.chat import Chat
from app.schemas.chat import ChatCreate, ChatRead, ContinueChatRequest
from app.services.audit_service import audit_service
from app.config import settings

router = APIRouter(prefix="/chats", tags=["Chats"])


# ── Create Chat ───────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatRead, status_code=201)
async def create_chat(
    data: ChatCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat inside a folder."""
    # Verify folder exists and user has access
    folder = await _get_folder_or_403(data.folder_id, current_user.id, db)

    chat = Chat(
        folder_id=folder.id,
        title=data.title or "New Chat",
        message_count=0,
    )
    db.add(chat)
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="chat_create",
        resource_type="chat",
        resource_id=str(chat.id),
        request=request,
        metadata={"folder_id": str(folder.id)},
    )

    return ChatRead.model_validate(chat)


# ── List Chats in Folder ──────────────────────────────────────────────────────

@router.get("/folder/{folder_id}", response_model=list[ChatRead])
async def list_chats_in_folder(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all chats in a folder."""
    await _get_folder_or_403(folder_id, current_user.id, db)

    result = await db.execute(
        select(Chat)
        .where(Chat.folder_id == folder_id, Chat.is_archived == False)
        .order_by(Chat.updated_at.desc())
    )
    chats = result.scalars().all()
    return [ChatRead.model_validate(c) for c in chats]


# ── Get Single Chat ───────────────────────────────────────────────────────────

@router.get("/{chat_id}", response_model=ChatRead)
async def get_chat(
    chat_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single chat with its details."""
    chat = await _get_chat_or_404(chat_id, db)
    await _check_chat_access(chat, current_user.id, db)

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="chat_open",
        resource_type="chat",
        resource_id=str(chat.id),
        request=request,
    )

    return ChatRead.model_validate(chat)


# ── Chat Continuation → Mini-Folder ──────────────────────────────────────────

@router.post("/{chat_id}/continue", response_model=dict)
async def continue_chat(
    chat_id: uuid.UUID,
    data: ContinueChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a mini-folder continuation of a chat.

    This is CLINICORE's signature feature:
    When a doctor needs to expand a conversation beyond the small-chat limit,
    they "continue" it — which creates:
    1. A mini-folder linked to this chat
    2. A new chat inside that mini-folder
    3. Carries forward the summary of the original chat as context

    Returns both the new folder and new chat IDs.
    """
    original_chat = await _get_chat_or_404(chat_id, db)
    await _check_chat_access(original_chat, current_user.id, db)

    # Check nesting depth limit
    parent_folder_result = await db.execute(
        select(Folder).where(Folder.id == original_chat.folder_id)
    )
    parent_folder = parent_folder_result.scalar_one_or_none()

    if parent_folder and parent_folder.depth >= settings.MAX_CONTINUATION_DEPTH:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum continuation depth ({settings.MAX_CONTINUATION_DEPTH}) reached. Cannot create deeper mini-folders.",
        )

    current_depth = parent_folder.depth if parent_folder else 0

    # Create the mini-folder
    mini_folder_name = (
        data.mini_folder_name
        or f"{original_chat.title} — Continued"
    )

    mini_folder = Folder(
        owner_id=current_user.id,
        name=mini_folder_name,
        description=data.continuation_reason,
        auth_level=parent_folder.auth_level if parent_folder else "standard",
        zero_retention_mode=parent_folder.zero_retention_mode if parent_folder else False,
        is_mini_folder=True,
        parent_chat_id=chat_id,
        depth=current_depth + 1,
    )
    db.add(mini_folder)
    await db.flush()

    # Create the first chat in the mini-folder
    # Pre-populate title from original chat + context from summary
    continuation_title = f"↪ {original_chat.title} (cont.)"
    new_chat = Chat(
        folder_id=mini_folder.id,
        title=continuation_title,
        summary=original_chat.summary,  # Carry forward summary as context seed
        is_mini_folder_root=True,
        continued_from_chat_id=chat_id,
        message_count=0,
    )
    db.add(new_chat)
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="chat_continue",
        resource_type="chat",
        resource_id=str(chat_id),
        request=request,
        metadata={
            "new_folder_id": str(mini_folder.id),
            "new_chat_id": str(new_chat.id),
            "depth": current_depth + 1,
        },
    )

    return {
        "message": "Mini-folder created successfully",
        "mini_folder": {
            "id": str(mini_folder.id),
            "name": mini_folder.name,
            "depth": mini_folder.depth,
            "parent_chat_id": str(chat_id),
        },
        "new_chat": {
            "id": str(new_chat.id),
            "title": new_chat.title,
            "folder_id": str(mini_folder.id),
        },
    }


# ── Archive Chat ──────────────────────────────────────────────────────────────

@router.post("/{chat_id}/archive")
async def archive_chat(
    chat_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive a chat (soft delete)."""
    chat = await _get_chat_or_404(chat_id, db)
    await _check_chat_access(chat, current_user.id, db)

    chat.is_archived = True
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="chat_archive",
        resource_type="chat",
        resource_id=str(chat.id),
        request=request,
    )

    return {"message": "Chat archived"}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_folder_or_403(
    folder_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> Folder:
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.owner_id == user_id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=403, detail="Folder not found or access denied")
    return folder


async def _get_chat_or_404(chat_id: uuid.UUID, db: AsyncSession) -> Chat:
    result = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


async def _check_chat_access(chat: Chat, user_id: uuid.UUID, db: AsyncSession):
    """Verify user owns the folder containing this chat."""
    result = await db.execute(
        select(Folder).where(Folder.id == chat.folder_id, Folder.owner_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")
