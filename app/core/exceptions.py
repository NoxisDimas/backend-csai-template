"""
Custom exception classes and global FastAPI exception handlers.

Design principle: Frontend clients receive only clean, generic error
messages. Raw stack traces are logged via structlog and dispatched
to the developer's Telegram bot.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.services.telegram_service import log_and_alert_error

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Custom Exception Hierarchy
# ---------------------------------------------------------------------------


class AppException(Exception):
    """Base application exception. All custom errors inherit from this."""

    def __init__(
        self,
        message: str = "An internal error occurred.",
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found (HTTP 404)."""

    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class AuthenticationError(AppException):
    """Authentication failure (HTTP 401)."""

    def __init__(self, message: str = "Invalid or expired authentication credentials.") -> None:
        super().__init__(message=message, code="AUTHENTICATION_FAILED", status_code=401)


class AuthorizationError(AppException):
    """Insufficient permissions (HTTP 403)."""

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message=message, code="FORBIDDEN", status_code=403)


class ValidationError(AppException):
    """Data validation error (HTTP 422)."""

    def __init__(
        self,
        message: str = "Validation failed.",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_FAILED",
            status_code=422,
            details=details,
        )


class ConflictError(AppException):
    """Resource conflict (HTTP 409)."""

    def __init__(self, message: str = "A resource conflict occurred.") -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409)


class RateLimitError(AppException):
    """Rate limit exceeded (HTTP 429)."""

    def __init__(self, message: str = "Too many requests. Please try again later.") -> None:
        super().__init__(message=message, code="RATE_LIMITED", status_code=429)


class ExternalServiceError(AppException):
    """External service failure (HTTP 502)."""

    def __init__(self, message: str = "An external service is currently unavailable.") -> None:
        super().__init__(message=message, code="EXTERNAL_SERVICE_ERROR", status_code=502)


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """Handle all custom AppException subclasses."""
        logger.error(
            "app_exception",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            path=str(request.url),
        )
        if exc.status_code >= 500:
            await log_and_alert_error(exc, "FastAPI Backend", "app_exception_handler", f"Handling request {request.method} {request.url.path}")
            
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle FastAPI's built-in HTTPException."""
        if exc.status_code >= 500:
            await log_and_alert_error(exc, "FastAPI Backend", "http_exception_handler", f"Handling request {request.method} {request.url.path}")
            
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc.detail),
                    "details": [],
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Catch-all handler for unhandled exceptions.

        - Logs the full stack trace via structlog.
        - Dispatches alert to Telegram.
        - Records silent error to DB.
        - Returns a clean, generic error response to the client.
        """
        logger.exception(
            "unhandled_exception",
            error_type=type(exc).__name__,
            error_message=str(exc),
            path=str(request.url),
        )
        
        # Fire to telegram & log to DB
        await log_and_alert_error(exc, "FastAPI Backend", "unhandled_exception", f"Handling request {request.method} {request.url.path}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An error occurred in the system. The technical team has been notified.",
                    "details": [],
                }
            },
        )
