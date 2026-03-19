"""
app/services/audit_service.py
──────────────────────────────
Audit logging service — creates immutable records of every significant action.

This is both a compliance requirement (HIPAA) and a security feature.
Every call to `log()` creates a new row in audit_logs — there are no
update or delete operations in this service.
"""

import uuid
from datetime import datetime
from typing import Optional
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.models.audit import AuditLog


class AuditService:
    """
    Use this as a dependency or call the module-level `audit()` function.

    Example:
        await audit_service.log(
            db=db,
            user_id=current_user.id,
            action="folder_open",
            resource_type="folder",
            resource_id=str(folder.id),
            request=request,
        )
    """

    async def log(
        self,
        db: AsyncSession,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request: Optional[Request] = None,
        metadata: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> AuditLog:
        """Create an audit log entry."""

        # Extract request context if available
        ip_address = None
        user_agent = None
        session_id = None

        if request:
            # Handle reverse proxy (X-Forwarded-For)
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                ip_address = forwarded_for.split(",")[0].strip()
            else:
                ip_address = request.client.host if request.client else None

            user_agent = request.headers.get("User-Agent", "")[:512]
            session_id = request.headers.get("X-Session-ID")

        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            metadata=metadata or {},
            notes=notes,
            timestamp=datetime.utcnow(),
        )

        db.add(entry)

        try:
            await db.flush()  # Write to DB without committing transaction
        except Exception as e:
            # Audit failures should not block the main request
            logger.error(f"Audit log write failed: {e}")

        return entry

    async def get_user_audit_trail(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 100,
        action_filter: Optional[str] = None,
    ) -> list[AuditLog]:
        """Retrieve audit logs for a specific user."""
        from sqlalchemy import select, desc

        query = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )

        if action_filter:
            query = query.where(AuditLog.action == action_filter)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_resource_audit_trail(
        self,
        db: AsyncSession,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get all actions performed on a specific resource."""
        from sqlalchemy import select, desc

        result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        return result.scalars().all()


# Singleton
audit_service = AuditService()
