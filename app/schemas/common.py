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

    timestamp: datetime = Field(default_factory=lambda: datetime.now(), description="The server time when the response was generated.")


class PaginationMeta(BaseModel):
    """Pagination metadata for paginated list responses."""

    total_items: int = Field(..., description="Total number of items across all pages.")
    total_pages: int = Field(..., description="Total number of available pages.")
    current_page: int = Field(..., description="The current page index (1-based).")
    per_page: int = Field(..., description="Number of items returned per page.")
    has_next: bool = Field(..., description="Whether there is a subsequent page.")
    has_prev: bool = Field(..., description="Whether there is a preceding page.")


class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response envelope.

    Usage:
        return SuccessResponse(data={"id": "...", "status": "active_ai"})
    """

    data: T = Field(..., description="The core data payload of the response.")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata.")


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

    data: list[T] = Field(..., description="List of items for the current page.")
    meta: ResponseMeta = Field(default_factory=ResponseMeta, description="Response metadata.")
    pagination: PaginationMeta = Field(..., description="Pagination metadata to assist UI navigation.")


# ---------------------------------------------------------------------------
# Error Response Envelope
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    """Individual field-level error detail."""

    field: str = Field(..., description="The name of the field that failed validation.")
    issue: str = Field(..., description="A human-readable description of why the field is invalid.")


class ErrorBody(BaseModel):
    """Error information body."""

    code: str = Field(..., description="A machine-readable error code (e.g. VALIDATION_FAILED).")
    message: str = Field(..., description="A user-friendly error message.")
    details: list[ErrorDetail] = Field(default_factory=list, description="Optional detailed list of validation errors per field.")


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

    error: ErrorBody = Field(..., description="The structured error envelope.")


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
