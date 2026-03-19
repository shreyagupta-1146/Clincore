"""
app/routers/auth.py
────────────────────
Authentication endpoints.

Auth0 handles the actual authentication flow (OAuth2, MFA).
These endpoints handle:
- User registration after first Auth0 login (sync user profile to DB)
- User profile reads/updates
- Token validation check (used by frontend to verify session)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.auth import get_current_user, verify_token
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead)
async def register_user(
    user_data: UserCreate,
    request: Request,
    credentials=Depends(__import__('fastapi.security', fromlist=['HTTPBearer']).HTTPBearer()),
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user after they've authenticated with Auth0.

    Flow:
    1. User logs in with Auth0 on the frontend
    2. Frontend gets a JWT token
    3. Frontend calls this endpoint with the token + profile data
    4. We verify the token and create the user in our DB

    This is called ONCE after a user's first login.
    """
    token = credentials.credentials
    payload = verify_token(token)
    auth0_sub = payload.get("sub")

    if not auth0_sub:
        raise HTTPException(status_code=400, detail="Invalid token: missing sub")

    # Check if user already exists
    result = await db.execute(select(User).where(User.auth0_sub == auth0_sub))
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    # Create new user
    new_user = User(
        auth0_sub=auth0_sub,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role,
        institution=user_data.institution,
        specialty=user_data.specialty,
    )
    db.add(new_user)
    await db.flush()

    await audit_service.log(
        db=db,
        user_id=new_user.id,
        action="user_registered",
        resource_type="user",
        resource_id=str(new_user.id),
        request=request,
        metadata={"role": user_data.role, "institution": user_data.institution},
    )

    return new_user


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get the current user's profile."""
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_profile(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile."""
    if updates.full_name is not None:
        current_user.full_name = updates.full_name
    if updates.institution is not None:
        current_user.institution = updates.institution
    if updates.specialty is not None:
        current_user.specialty = updates.specialty

    await db.flush()
    return current_user


@router.get("/verify")
async def verify_session(current_user: User = Depends(get_current_user)):
    """Quick token verification endpoint. Returns 200 if valid, 401 if not."""
    return {"valid": True, "user_id": str(current_user.id), "role": current_user.role}
