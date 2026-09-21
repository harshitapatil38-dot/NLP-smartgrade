"""Pydantic schemas for the chat and health API endpoints."""

from typing import Optional, List
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for the POST /api/v1/chat endpoint."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The natural-language question to ask the college assistant.",
        json_schema_extra={"examples": ["What documents are required for admission?"]},
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session identifier to continue an existing conversation.",
    )


class SourceInfo(BaseModel):
    """Source metadata for a single retrieved chunk."""
    document_id: int
    document_version_id: int
    chunk_id: int
    title: Optional[str] = None
    source: Optional[str] = None
    page_number: Optional[int] = None
    similarity_score: Optional[float] = None
    department: Optional[str] = None


class ChatResponse(BaseModel):
    """Response body for the POST /api/v1/chat endpoint."""
    session_id: str = Field(description="The unique identifier for the current chat session.")
    answer: str = Field(description="The generated answer based on college knowledge.")
    sources: List[SourceInfo] = Field(
        default_factory=list,
        description="Source references for the retrieved knowledge chunks.",
    )
    query: str = Field(description="The original question that was asked.")
    retrieved_chunks: int = Field(
        default=0,
        description="Number of knowledge chunks used to build the context.",
    )
    context_truncated: bool = Field(
        default=False,
        description="Whether the context was truncated due to length limits.",
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Response body for the GET /api/v1/health endpoint."""
    status: str = "ok"
    service: str = "PCCOE College AI Assistant API"


class ReadinessResponse(BaseModel):
    """Response body for the GET /api/v1/health/ready endpoint."""
    status: str
    database: str
    embedding_model: str
    llm_provider: str


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Detailed information about an API error."""
    code: str = Field(description="Internal error code (e.g., VALIDATION_ERROR).")
    message: str = Field(description="Human-readable error message.")
    request_id: Optional[str] = Field(default=None, description="Request correlation ID.")


class ErrorResponse(BaseModel):
    """Standard structured error response."""
    error: ErrorDetail
