"""
Authentication endpoints: login, register, and current user profile.

- POST /auth/login — Authenticate and receive JWT
- POST /auth/register — Create new user (admin-only)
- GET /auth/me — Get current user profile
"""

from typing import List
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin, get_current_superadmin, get_current_user, get_db
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserResponse, UserUpdate
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=SuccessResponse[TokenResponse],
    summary="Login",
    description="Authenticate with email and password. Returns a JWT access token.",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[TokenResponse]:
    """Authenticate user and return JWT token."""
    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")

    token = create_access_token(data={"sub": str(user.id)})

    return SuccessResponse(
        data=TokenResponse(access_token=token)
    )


@router.post(
    "/register",
    response_model=SuccessResponse[UserResponse],
    status_code=201,
    summary="Register User",
    description="Create a new dashboard user. Requires superadmin privileges.",
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_superadmin),
) -> SuccessResponse[UserResponse]:
    """Create a new user account (superadmin-only)."""
    # Check for existing email
    existing = await db.execute(
        select(User).where(User.email == payload.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A user with this email already exists.")

    new_user = User(
        name=payload.name,
        email=payload.email,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return SuccessResponse(
        data=UserResponse.model_validate(new_user)
    )


@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="Current User",
    description="Get the profile of the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[UserResponse]:
    """Return the current user's profile."""
    return SuccessResponse(
        data=UserResponse.model_validate(current_user)
    )


@router.put(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="Update Current User",
    description="Update password, email, or nickname (name) of the current user.",
)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse[UserResponse]:
    """Update current user profile."""
    if payload.email and payload.email != current_user.email:
        # Check if email is taken
        existing = await db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("A user with this email already exists.")
        current_user.email = payload.email
        
    if payload.name:
        current_user.name = payload.name
        
    if payload.password:
        current_user.password_hash = hash_password(payload.password)
        
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return SuccessResponse(
        data=UserResponse.model_validate(current_user)
    )

@router.get(
    "/users",
    response_model=SuccessResponse[List[UserResponse]],
    summary="List All Users",
    description="Get a list of all registered users. Requires admin privileges.",
)
async def get_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> SuccessResponse[List[UserResponse]]:
    """Return all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return SuccessResponse(
        data=[UserResponse.model_validate(u) for u in users]
    )

@router.put(
    "/users/{user_id}",
    response_model=SuccessResponse[UserResponse],
    summary="Update User",
    description="Update a user's details. Requires superadmin privileges.",
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_superadmin),
) -> SuccessResponse[UserResponse]:
    """Update a user's profile (superadmin-only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user_to_update = result.scalar_one_or_none()
    if not user_to_update:
        raise NotFoundError("User not found.")

    if payload.email and payload.email != user_to_update.email:
        existing = await db.execute(select(User).where(User.email == payload.email))
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("A user with this email already exists.")
        user_to_update.email = payload.email
        
    if payload.name:
        user_to_update.name = payload.name
        
    if payload.password:
        user_to_update.password_hash = hash_password(payload.password)
        
    # Assuming role is part of UserUpdate schema, if not we ignore it or add it
    if hasattr(payload, "role") and getattr(payload, "role"):
        user_to_update.role = getattr(payload, "role")
        
    db.add(user_to_update)
    await db.commit()
    await db.refresh(user_to_update)
    
    return SuccessResponse(
        data=UserResponse.model_validate(user_to_update)
    )

@router.delete(
    "/users/{user_id}",
    response_model=SuccessResponse[dict],
    summary="Delete User",
    description="Delete a user. Requires superadmin privileges.",
)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_superadmin),
) -> SuccessResponse[dict]:
    """Delete a user account (superadmin-only)."""
    if str(current_admin.id) == str(user_id):
        raise ConflictError("You cannot delete your own account.")
        
    result = await db.execute(select(User).where(User.id == user_id))
    user_to_delete = result.scalar_one_or_none()
    if not user_to_delete:
        raise NotFoundError("User not found.")
        
    await db.delete(user_to_delete)
    await db.commit()
    
    return SuccessResponse(
        data={"message": "User deleted successfully."}
    )
