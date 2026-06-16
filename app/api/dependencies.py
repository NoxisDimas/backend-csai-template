"""
Shared API dependencies for FastAPI's Depends() injection system.

Provides:
    - get_db: Async database session
    - get_current_user: JWT token verification + user lookup
    - get_current_admin: Admin role enforcement
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import verify_access_token
from app.db.session import get_db as _get_db
from app.models.user import User


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Yield an async database session. Alias for db.session.get_db."""
    async for session in _get_db():
        yield session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and verify JWT from Authorization header, then load user from DB.

    Raises:
        AuthenticationError: If token is missing, invalid, or user not found.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Missing or malformed Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_access_token(token)

    if payload is None:
        raise AuthenticationError("Invalid or expired token.")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token payload missing subject claim.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found.")

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify the current user has admin role.

    Raises:
        AuthorizationError: If user is not an admin.
    """
    if current_user.role not in ("admin", "superadmin"):
        raise AuthorizationError("Admin privileges required.")
    return current_user


async def get_current_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify the current user has superadmin role.

    Raises:
        AuthorizationError: If user is not a superadmin.
    """
    if current_user.role != "superadmin":
        raise AuthorizationError("Superadmin privileges required.")
    return current_user
