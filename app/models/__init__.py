"""
app/models/__init__.py
──────────────────────
Exports all models so `create_tables()` can find them via metadata.
"""

from app.models.user import User
from app.models.folder import Folder
from app.models.chat import Chat
from app.models.message import Message
from app.models.share import Share, ShareAudit
from app.models.audit import AuditLog

__all__ = [
    "User",
    "Folder",
    "Chat",
    "Message",
    "Share",
    "ShareAudit",
    "AuditLog",
]
