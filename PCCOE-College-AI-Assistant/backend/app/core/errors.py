import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.api import ErrorResponse, ErrorDetail
from app.core.exceptions import KnowledgeBaseException
from app.services.llm_service import LLMServiceError
from app.core.middleware import get_request_id

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI):
    """Register global exception handlers for the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error: {exc.errors()} [req_id={get_request_id()}]")
        error_detail = ErrorDetail(
            code="VALIDATION_ERROR",
            message="The request contains invalid data.",
            request_id=get_request_id()
        )
        return JSONResponse(status_code=400, content={"error": error_detail.model_dump()})

    @app.exception_handler(KnowledgeBaseException)
    async def domain_exception_handler(request: Request, exc: KnowledgeBaseException):
        logger.warning(f"Domain error: {str(exc)} [req_id={get_request_id()}]")
        error_detail = ErrorDetail(
            code="DOMAIN_ERROR",
            message=str(exc),
            request_id=get_request_id()
        )
        return JSONResponse(status_code=400, content={"error": error_detail.model_dump()})

    @app.exception_handler(LLMServiceError)
    async def llm_exception_handler(request: Request, exc: LLMServiceError):
        logger.error(f"LLM Service Error: {str(exc)} [req_id={get_request_id()}]")
        error_detail = ErrorDetail(
            code="LLM_SERVICE_ERROR",
            message="The AI assistant is temporarily unavailable or returned an invalid response. Please try again.",
            request_id=get_request_id()
        )
        return JSONResponse(status_code=503, content={"error": error_detail.model_dump()})

    @app.exception_handler(SQLAlchemyError)
    async def database_exception_handler(request: Request, exc: SQLAlchemyError):
        # Log the actual database error but don't expose it to the user
        logger.error(f"Database error: {str(exc)} [req_id={get_request_id()}]")
        error_detail = ErrorDetail(
            code="DATABASE_ERROR",
            message="An internal database error occurred.",
            request_id=get_request_id()
        )
        return JSONResponse(status_code=500, content={"error": error_detail.model_dump()})

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unexpected error: {str(exc)} [req_id={get_request_id()}]")
        error_detail = ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Please try again later.",
            request_id=get_request_id()
        )
        return JSONResponse(status_code=500, content={"error": error_detail.model_dump()})
