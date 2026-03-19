"""
app/routers/folders.py
───────────────────────
Folder management endpoints.

Key security feature: Folder access respects auth_level.
- STANDARD folders: any logged-in user can access (if they own it / have share)
- STEP_UP folders: require re-authentication (MFA prompt via Auth0)
- HIGH_SECURITY folders: require step-up + IP restriction (future)
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.auth import get_current_user, require_stepup_auth, check_folder_auth
from app.models.user import User
from app.models.folder import Folder, FolderAuthLevel
from app.models.chat import Chat
from app.schemas.folder import FolderCreate, FolderRead, FolderUpdate
from app.services.audit_service import audit_service
from app.config import settings

router = APIRouter(prefix="/folders", tags=["Folders"])


# ── Create Folder ─────────────────────────────────────────────────────────────

@router.post("/", response_model=FolderRead, status_code=201)
async def create_folder(
    data: FolderCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new top-level folder."""
    folder = Folder(
        owner_id=current_user.id,
        name=data.name,
        description=data.description,
        color=data.color,
        auth_level=data.auth_level,
        zero_retention_mode=data.zero_retention_mode,
        is_mini_folder=False,
        depth=0,
    )
    db.add(folder)
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="folder_create",
        resource_type="folder",
        resource_id=str(folder.id),
        request=request,
        metadata={"name": folder.name, "auth_level": folder.auth_level},
    )

    return _folder_to_read(folder, 0)


# ── List Folders ──────────────────────────────────────────────────────────────

@router.get("/", response_model=list[FolderRead])
async def list_folders(
    include_mini_folders: bool = Query(False),
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all folders owned by the current user."""
    query = select(Folder).where(Folder.owner_id == current_user.id)

    if not include_mini_folders:
        query = query.where(Folder.is_mini_folder == False)

    if not include_archived:
        query = query.where(Folder.is_archived == False)

    result = await db.execute(query)
    folders = result.scalars().all()

    # Add chat counts
    folder_reads = []
    for folder in folders:
        count_result = await db.execute(
            select(func.count(Chat.id)).where(Chat.folder_id == folder.id)
        )
        chat_count = count_result.scalar()
        folder_reads.append(_folder_to_read(folder, chat_count))

    return folder_reads


# ── Get / Open Folder (respects auth_level) ───────────────────────────────────

@router.get("/{folder_id}", response_model=FolderRead)
async def get_folder(
    folder_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get folder details. Enforces auth_level:
    - STANDARD: any authenticated user (if owner or has share)
    - STEP_UP: returns 403 with detail="step_up_required" → frontend triggers MFA
    """
    folder = await _get_folder_or_404(folder_id, db)
    await _check_folder_access(folder, current_user, request)

    if folder.auth_level == FolderAuthLevel.STEP_UP:
        # Frontend should detect this and redirect to step-up auth
        # If they have the step-up token, the /stepup endpoint handles it
        raise HTTPException(status_code=403, detail="step_up_required")

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="folder_open",
        resource_type="folder",
        resource_id=str(folder.id),
        request=request,
    )

    count_result = await db.execute(
        select(func.count(Chat.id)).where(Chat.folder_id == folder.id)
    )
    return _folder_to_read(folder, count_result.scalar())


@router.get("/{folder_id}/stepup", response_model=FolderRead)
async def get_folder_with_stepup(
    folder_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_stepup_auth),  # requires MFA re-auth
    db: AsyncSession = Depends(get_db),
):
    """
    Open a STEP_UP folder after successful re-authentication.
    The frontend redirects here after the Auth0 step-up flow completes.
    """
    folder = await _get_folder_or_404(folder_id, db)
    await _check_folder_access(folder, current_user, request)

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="folder_stepup_open",
        resource_type="folder",
        resource_id=str(folder.id),
        request=request,
        metadata={"auth_method": "stepup_mfa"},
    )

    count_result = await db.execute(
        select(func.count(Chat.id)).where(Chat.folder_id == folder.id)
    )
    return _folder_to_read(folder, count_result.scalar())


# ── Update / Archive Folder ───────────────────────────────────────────────────

@router.patch("/{folder_id}", response_model=FolderRead)
async def update_folder(
    folder_id: uuid.UUID,
    data: FolderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update folder name, description, color, or auth level."""
    folder = await _get_folder_or_404(folder_id, db)

    if folder.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the folder owner can modify it")

    if data.name is not None:
        folder.name = data.name
    if data.description is not None:
        folder.description = data.description
    if data.color is not None:
        folder.color = data.color
    if data.auth_level is not None:
        folder.auth_level = data.auth_level

    await db.flush()

    count_result = await db.execute(
        select(func.count(Chat.id)).where(Chat.folder_id == folder.id)
    )
    return _folder_to_read(folder, count_result.scalar())


@router.post("/{folder_id}/archive")
async def archive_folder(
    folder_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Archive a folder (soft delete)."""
    folder = await _get_folder_or_404(folder_id, db)

    if folder.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the folder owner can archive it")

    folder.is_archived = True
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=current_user.id,
        action="folder_archive",
        resource_type="folder",
        resource_id=str(folder.id),
        request=request,
    )

    return {"message": "Folder archived", "folder_id": str(folder.id)}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_folder_or_404(folder_id: uuid.UUID, db: AsyncSession) -> Folder:
    result = await db.execute(select(Folder).where(Folder.id == folder_id))
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


async def _check_folder_access(folder: Folder, current_user: User, request: Request):
    """Check if current_user can access this folder (ownership or share)."""
    if folder.owner_id == current_user.id:
        return  # Owner always has access

    # TODO: Check share table for access grants
    # This is expanded in the shares router
    raise HTTPException(status_code=403, detail="Access denied")


def _folder_to_read(folder: Folder, chat_count: int) -> FolderRead:
    return FolderRead(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        color=folder.color,
        auth_level=folder.auth_level,
        zero_retention_mode=folder.zero_retention_mode,
        is_mini_folder=folder.is_mini_folder,
        parent_chat_id=folder.parent_chat_id,
        depth=folder.depth,
        is_archived=folder.is_archived,
        chat_count=chat_count,
        created_at=folder.created_at,
    )
