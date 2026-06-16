"""
Standardized response envelope schemas and pagination support.

All Backend REST APIs use these envelopes so the Frontend has a
predictable structure for handling loading, success, and error states.

Reference: docs/data-contracts.md
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Success Response Envelope
# ---------------------------------------------------------------------------


class ResponseMeta(BaseModel):
    """Metadata attached to successful responses."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class PaginationMeta(BaseModel):
    """Pagination metadata for paginated list responses."""

    total_items: int
    total_pages: int
    current_page: int
    per_page: int
    has_next: bool
    has_prev: bool


class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response envelope.

    Usage:
        return SuccessResponse(data={"id": "...", "status": "active_ai"})
    """

    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated success response envelope for list endpoints.

    Usage:
        return PaginatedResponse(
            data=[...],
            meta=ResponseMeta(),
            pagination=PaginationMeta(...)
        )
    """

    data: list[T]
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
    pagination: PaginationMeta


# ---------------------------------------------------------------------------
# Error Response Envelope
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Individual field-level error detail."""

    field: str
    issue: str


class ErrorBody(BaseModel):
    """Error information body."""

    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """
    Standard error response envelope.

    The Frontend parses this structure for toast notifications and
    form validation error display.

    Usage:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorBody(
                    code="VALIDATION_FAILED",
                    message="Invalid Shopify domain.",
                    details=[ErrorDetail(field="shopify_domain", issue="...")]
                )
            ).model_dump()
        )
    """

    error: ErrorBody


# ---------------------------------------------------------------------------
# Common Query Parameters
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    """Common pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class MessageResponse(BaseModel):
    """Simple message response for action confirmations."""

    success: bool = True
    message: str


class StatusResponse(BaseModel):
    """Response for async processing acknowledgments (202 Accepted)."""

    status: str = "processing"
    detail: str | None = None
    id: Any | None = None
