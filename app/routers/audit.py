"""
app/routers/audit.py
─────────────────────
Audit trail endpoints — for compliance and security review.
"""

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.services.audit_service import audit_service
from fastapi import HTTPException

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/my-activity")
async def get_my_audit_trail(
    limit: int = Query(50, le=200),
    action: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's own audit trail."""
    logs = await audit_service.get_user_audit_trail(
        db=db,
        user_id=current_user.id,
        limit=limit,
        action_filter=action,
    )
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address,
            "event_data": log.event_data,
        }
        for log in logs
    ]


@router.get("/folder/{folder_id}")
async def get_folder_audit_trail(
    folder_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all access logs for a specific folder. Only folder owner can view."""
    # Verify ownership
    from sqlalchemy import select
    from app.models.folder import Folder

    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.owner_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    logs = await audit_service.get_resource_audit_trail(
        db=db,
        resource_type="folder",
        resource_id=str(folder_id),
    )

    return [
        {
            "action": log.action,
            "user_id": str(log.user_id) if log.user_id else None,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address,
            "event_data": log.event_data,
        }
        for log in logs
    ]
