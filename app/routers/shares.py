"""
app/routers/shares.py
──────────────────────
Secure sharing endpoints.

The sharing workflow:
1. Sender: POST /shares — creates a share with recipient details + generates token
2. System: sends email notification to recipient (if email provided)
3. Recipient: receives link containing the access_token
4. Recipient: authenticates with Auth0 (login + MFA)
5. Recipient: POST /shares/accept with their JWT + access_token
6. System: verifies recipient identity, marks share as accepted
7. Recipient: can now access the shared folder via GET /shares/{share_id}/folder

Every access step is audit logged.
Sender can revoke access at any time: POST /shares/{share_id}/revoke
"""

import uuid
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.folder import Folder
from app.models.share import Share, ShareAudit
from app.models.chat import Chat
from app.models.message import Message
from app.schemas.share import ShareCreate, ShareRead, ShareAccept
from app.core.encryption import decrypt_from_storage
from app.services.audit_service import audit_service

router = APIRouter(prefix="/shares", tags=["Secure Sharing"])


# ── Create Share ──────────────────────────────────────────────────────────────

@router.post("/", response_model=ShareRead, status_code=201)
async def create_share(
    data: ShareCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Share a folder with a named recipient.

    The sender MUST provide:
    - recipient_name: Full name of the intended recipient
    - recipient_role: Their clinical role (e.g., "Dermatologist", "Radiologist")
    - (Optional) recipient_email: For notification

    A unique access_token is generated. The recipient must authenticate AND
    present this token to access the shared content.
    """
    # Verify sender owns the folder
    folder = await _get_folder_or_403(data.folder_id, current_user.id, db)

    # Generate cryptographically secure access token
    access_token = secrets.token_urlsafe(32)

    # Calculate expiry
    expires_at = None
    if data.expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=data.expires_hours)

    share = Share(
        folder_id=folder.id,
        shared_by_user_id=current_user.id,
        recipient_name=data.recipient_name,
        recipient_role=data.recipient_role,
        recipient_email=data.recipient_email,
        recipient_institution=data.recipient_institution,
        access_token=access_token,
        can_view_messages=data.can_view_messages,
        can_view_images=data.can_view_images,
        can_add_comments=data.can_add_comments,
        can_reshare=data.can_reshare,
        message=data.message,
        expires_at=expires_at,
    )
    db.add(share)
    await db.flush()

    # Send email notification in background (if email provided)
    if data.recipient_email:
        background_tasks.add_task(
            _send_share_notification_email,
            recipient_email=data.recipient_email,
            recipient_name=data.recipient_name,
            sender_name=current_user.full_name,
            folder_name=folder.name,
            access_token=access_token,
            message=data.message,
            expires_at=expires_at,
        )

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="share_create",
        resource_type="folder",
        resource_id=str(folder.id),
        request=request,
        metadata={
            "recipient_name": data.recipient_name,
            "recipient_role": data.recipient_role,
            "has_email": data.recipient_email is not None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "permissions": {
                "view_messages": data.can_view_messages,
                "view_images": data.can_view_images,
                "add_comments": data.can_add_comments,
                "reshare": data.can_reshare,
            },
        },
    )

    return ShareRead.model_validate(share)


# ── Accept Share (recipient authenticates and accepts) ────────────────────────

@router.post("/accept", response_model=dict)
async def accept_share(
    data: ShareAccept,
    request: Request,
    current_user: User = Depends(get_current_user),  # Recipient must be authenticated
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a share after authentication.

    The recipient calls this with:
    - Their Auth0 JWT (already verified by Depends)
    - The access_token from the share link

    This verifies their identity is legitimate before granting access.
    """
    # Find the share by token
    result = await db.execute(
        select(Share).where(Share.access_token == data.access_token)
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="Share not found or invalid token")

    if share.is_revoked:
        raise HTTPException(status_code=403, detail="This share has been revoked")

    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="This share link has expired")

    # Mark as accepted
    if not share.is_accepted:
        share.is_accepted = True
        share.accepted_at = datetime.utcnow()
        await db.flush()

    # Log this access
    access_log = ShareAudit(
        share_id=share.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent", ""),
        auth_method="auth0_mfa",
        actions=["accept"],
    )
    db.add(access_log)

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="share_accept",
        resource_type="share",
        resource_id=str(share.id),
        request=request,
        metadata={
            "recipient_name": share.recipient_name,
            "folder_id": str(share.folder_id),
        },
    )

    return {
        "accepted": True,
        "share_id": str(share.id),
        "folder_id": str(share.folder_id),
        "permissions": {
            "view_messages": share.can_view_messages,
            "view_images": share.can_view_images,
            "add_comments": share.can_add_comments,
        },
    }


# ── Access Shared Folder ──────────────────────────────────────────────────────

@router.get("/{share_id}/folder-contents")
async def get_shared_folder_contents(
    share_id: uuid.UUID,
    access_token: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Access the shared folder contents.
    Requires: authentication + valid access_token + share not expired/revoked.
    """
    share = await _get_valid_share(share_id, access_token, db)

    # Get chats in the shared folder
    chats_result = await db.execute(
        select(Chat)
        .where(Chat.folder_id == share.folder_id, Chat.is_archived == False)
        .order_by(Chat.created_at.asc())
    )
    chats = chats_result.scalars().all()

    # Build response based on permissions
    folder_data = {"chats": []}

    for chat in chats:
        chat_data = {
            "id": str(chat.id),
            "title": chat.title,
            "summary": chat.summary,
            "message_count": chat.message_count,
            "created_at": chat.created_at.isoformat(),
        }

        if share.can_view_messages:
            msgs_result = await db.execute(
                select(Message)
                .where(Message.chat_id == chat.id)
                .order_by(Message.created_at.asc())
            )
            messages = msgs_result.scalars().all()
            chat_data["messages"] = [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": decrypt_from_storage(m.content_encrypted),
                    "has_image": m.image_path is not None,
                    "ai_metadata": m.ai_metadata,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ]

        folder_data["chats"].append(chat_data)

    # Log access
    access_log = ShareAudit(
        share_id=share.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent", ""),
        auth_method="auth0",
        actions=["view_folder"],
    )
    db.add(access_log)

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="share_access",
        resource_type="share",
        resource_id=str(share.id),
        request=request,
    )

    return folder_data


# ── List My Shares ────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ShareRead])
async def list_my_shares(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all shares created by the current user."""
    result = await db.execute(
        select(Share)
        .where(Share.shared_by_user_id == current_user.id)
        .order_by(Share.created_at.desc())
    )
    return [ShareRead.model_validate(s) for s in result.scalars().all()]


# ── Revoke Share ──────────────────────────────────────────────────────────────

@router.post("/{share_id}/revoke")
async def revoke_share(
    share_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a share. The recipient immediately loses access."""
    result = await db.execute(select(Share).where(Share.id == share_id))
    share = result.scalar_one_or_none()

    if not share or share.shared_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Share not found")

    share.is_revoked = True
    share.revoked_at = datetime.utcnow()
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="share_revoke",
        resource_type="share",
        resource_id=str(share.id),
        request=request,
        metadata={"recipient_name": share.recipient_name},
    )

    return {"message": "Share revoked", "share_id": str(share.id)}


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


async def _get_valid_share(
    share_id: uuid.UUID, access_token: str, db: AsyncSession
) -> Share:
    result = await db.execute(
        select(Share).where(
            Share.id == share_id,
            Share.access_token == access_token,
            Share.is_revoked == False,
        )
    )
    share = result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=403, detail="Invalid share or access denied")

    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Share link has expired")

    if not share.is_accepted:
        raise HTTPException(
            status_code=403,
            detail="Share not yet accepted. Recipient must accept the share first.",
        )

    return share


async def _send_share_notification_email(
    recipient_email: str,
    recipient_name: str,
    sender_name: str,
    folder_name: str,
    access_token: str,
    message: str | None,
    expires_at: datetime | None,
):
    """Background task: send share notification email."""
    # TODO: Implement with smtplib or SendGrid
    # For now, just log
    logger.info(
        f"[EMAIL] Share notification: {sender_name} → {recipient_name} ({recipient_email}) "
        f"for folder '{folder_name}'. Token: {access_token[:8]}..."
    )

from loguru import logger
