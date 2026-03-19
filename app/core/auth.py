"""
app/core/auth.py
────────────────
Auth0 JWT validation for FastAPI.

Every protected route uses `get_current_user` as a dependency.
The JWT token is extracted from the Authorization: Bearer header,
validated against Auth0's JWKS endpoint, and the user is loaded from DB.

Step-up authentication (folder-level) is handled separately via
`require_stepup_auth` — this checks for an additional claim in the JWT
that Auth0's step-up Action adds after MFA re-verification.
"""

import uuid
from typing import Optional
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.services.audit_service import AuditService

# ── JWT Bearer scheme ──────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=True)


@lru_cache()
def get_jwks_client() -> PyJWKClient:
    """Cached JWKS client — fetches Auth0 public keys once and caches them."""
    return PyJWKClient(settings.auth0_jwks_url, cache_keys=True)


def verify_token(token: str) -> dict:
    """
    Verify and decode an Auth0 JWT token.
    Raises HTTPException(401) if invalid.
    """
    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=settings.auth0_issuer,
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validates the JWT and returns the current User.

    Usage:
        @router.get("/me")
        async def get_me(current_user: User = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials
    payload = verify_token(token)

    auth0_sub = payload.get("sub")
    if not auth0_sub:
        raise HTTPException(status_code=401, detail="Invalid token: missing sub")

    # Load user from database
    result = await db.execute(
        select(User).where(User.auth0_sub == auth0_sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found. Please complete registration.",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")

    # Log this request context for audit service
    request.state.current_user = user
    request.state.jwt_payload = payload

    return user


async def require_stepup_auth(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> User:
    """
    Dependency for folder-level step-up authentication.

    Auth0's Step-Up Authentication Action adds a custom claim
    `https://clinicore.ai/stepup` to the JWT after the user completes
    an additional MFA challenge. This dependency checks for that claim.

    Frontend flow:
    1. User tries to open a STEP_UP folder
    2. Gets 403 from this dependency
    3. Frontend redirects to Auth0 step-up flow
    4. Auth0 issues new token with stepup claim
    5. User retries with new token → access granted

    See: https://auth0.com/docs/secure/multi-factor-authentication/step-up-authentication
    """
    token = credentials.credentials
    payload = verify_token(token)

    # Check for step-up claim (added by Auth0 Action after MFA)
    stepup_verified = payload.get("https://clinicore.ai/stepup", False)
    stepup_time = payload.get("https://clinicore.ai/stepup_time", 0)

    if not stepup_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="step_up_required",
            # Frontend uses this exact string to trigger the step-up flow
        )

    # Step-up tokens should be fresh (within last 15 minutes)
    import time
    if time.time() - stepup_time > 900:  # 15 minutes
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="step_up_expired",
        )

    return current_user


def check_folder_auth(folder, current_user: User, is_stepup: bool = False) -> None:
    """
    Checks if current_user has permission to access a folder based on
    the folder's auth_level. Call this in folder-access endpoints.
    """
    from app.models.folder import FolderAuthLevel

    # Owner always has access
    if folder.owner_id == current_user.id:
        return

    # Check auth level requirements
    if folder.auth_level == FolderAuthLevel.STEP_UP and not is_stepup:
        raise HTTPException(
            status_code=403,
            detail="step_up_required",
        )

    if folder.auth_level == FolderAuthLevel.HIGH_SECURITY and not is_stepup:
        raise HTTPException(
            status_code=403,
            detail="high_security_folder_requires_stepup_and_mfa",
        )
