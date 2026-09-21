import uuid
import time
import logging
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Context variable to hold the request ID for the current request
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Get request ID from header or generate a new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Set context variable
        token = request_id_var.set(request_id)
        
        start_time = time.time()
        
        # Log request start (only basic info, no sensitive data)
        logger.info(f"Request started: {request.method} {request.url.path} [req_id={request_id}]")
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} "
                f"- Duration: {process_time:.3f}s [req_id={request_id}]"
            )
            
            # Add request ID to response header
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- Duration: {process_time:.3f}s [req_id={request_id}]",
                exc_info=True
            )
            raise
        finally:
            request_id_var.reset(token)

def get_request_id() -> str:
    """Helper to get the current request ID."""
    return request_id_var.get()
