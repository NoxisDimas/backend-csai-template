"""
Authentication endpoints: login, register, and current user profile.

- POST /auth/login — Authenticate and receive JWT
- POST /auth/register — Create new user (admin-only)
- GET /auth/me — Get current user profile
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin, get_current_superadmin, get_current_user, get_db
from app.core.exceptions import AuthenticationError, ConflictError
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
