"""
Authentication middleware and dependencies.

Provides FastAPI dependencies for:
- Getting the current authenticated user
- Role-based access control
- Organization context
"""

from typing import Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = structlog.get_logger()

# Bearer token security scheme
security = HTTPBearer(auto_error=False)


class CurrentUser:
    """Current authenticated user context."""

    def __init__(
        self,
        id: str,
        email: str,
        org_id: str,
        role: str = "member",
        is_active: bool = True,
    ):
        self.id = id
        self.email = email
        self.org_id = org_id
        self.role = role
        self.is_active = is_active


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    Get the current authenticated user from the JWT token.

    This is a placeholder implementation for development.
    In production, this should validate the JWT token and fetch the user.
    """
    # TODO: Implement proper JWT validation
    # For now, return a placeholder user for development
    if credentials is None:
        # Allow unauthenticated access in development with placeholder
        return CurrentUser(
            id="dev-user-id",
            email="dev@example.com",
            org_id="dev-org-id",
            role="admin",
            is_active=True,
        )

    # In production, validate token and fetch user
    # token = credentials.credentials
    # try:
    #     payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    #     user_id = payload.get("sub")
    #     # Fetch user from database
    # except jwt.ExpiredSignatureError:
    #     raise HTTPException(status_code=401, detail="Token expired")
    # except jwt.JWTError:
    #     raise HTTPException(status_code=401, detail="Invalid token")

    return CurrentUser(
        id="dev-user-id",
        email="dev@example.com",
        org_id="dev-org-id",
        role="admin",
        is_active=True,
    )


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Ensure the current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def require_admin(
    current_user: CurrentUser = Depends(get_current_active_user),
) -> CurrentUser:
    """Require admin role."""
    if current_user.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_owner(
    current_user: CurrentUser = Depends(get_current_active_user),
) -> CurrentUser:
    """Require owner role."""
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return current_user
