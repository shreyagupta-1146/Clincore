"""app/schemas/user.py"""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.DOCTOR
    institution: str | None = None
    specialty: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    institution: str | None
    specialty: str | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: str | None = None
    institution: str | None = None
    specialty: str | None = None
