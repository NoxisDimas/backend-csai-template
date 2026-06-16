import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure every request has an X-Correlation-ID header.
    It binds the correlation ID to the structlog context so all logs
    generated during the request share the same tracking ID.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check if the header already exists (e.g., passed by Nginx)
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            # Generate a new one if not present
            correlation_id = str(uuid.uuid4())
            
        # Bind the ID to the structlog context for the duration of this request
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        
        # Process the request
        response = await call_next(request)
        
        # Ensure the response also includes the correlation ID
        response.headers["X-Correlation-ID"] = correlation_id
        
        # Unbind specifically the correlation_id (optional, contextvars naturally isolate per task)
        structlog.contextvars.unbind_contextvars("correlation_id")
        
        return response
