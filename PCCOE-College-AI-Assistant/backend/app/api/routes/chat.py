"""
Chat API route — POST /api/v1/chat

Accepts a natural-language question and returns a grounded answer
with source references from the college knowledge base.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.api import ChatRequest, ChatResponse, SourceInfo, ErrorResponse
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask the college assistant a question",
    description=(
        "Submit a natural-language question about PCCOE college. "
        "The system retrieves relevant official knowledge, builds context, "
        "and generates a grounded answer with source references."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "LLM service unavailable"},
    },
)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Handle a chat question through the full RAG pipeline."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    chat_service = ChatService(db)
    session_id, result = chat_service.process_chat(question, request.session_id)

    # Convert dataclass SourceReferences to Pydantic SourceInfo
    sources = [
        SourceInfo(
            document_id=s.document_id,
            document_version_id=s.document_version_id,
            chunk_id=s.chunk_id,
            title=s.title,
            source=s.source,
            page_number=s.page_number,
            similarity_score=s.similarity_score,
            department=s.department,
        )
        for s in result.sources
    ]

    return ChatResponse(
        session_id=session_id,
        answer=result.answer,
        sources=sources,
        query=result.query,
        retrieved_chunks=result.retrieved_chunks,
        context_truncated=result.context_truncated,
    )
