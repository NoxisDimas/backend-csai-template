"""
Pydantic schemas for authentication endpoints.

Handles login, registration, token responses, and user profile data.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Account password")


class TokenResponse(BaseModel):
    """JWT token response after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Request payload to create a new user (admin-only)."""

    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Must be at least 8 characters")
    role: str = Field(
        ...,
        pattern="^(admin|staff)$",
        description="User role: admin or staff",
    )


class UserResponse(BaseModel):
    """Public user profile response (excludes password_hash)."""

    id: uuid.UUID
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Request payload to update user profile."""

    name: str | None = Field(None, min_length=1, max_length=150)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, description="Must be at least 8 characters")
