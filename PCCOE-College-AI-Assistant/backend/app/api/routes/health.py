"""
Health API routes — GET /api/v1/health and /api/v1/health/ready

Basic liveness check and infrastructure readiness probe.
"""

import os
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.database import get_db
from app.schemas.api import HealthResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic liveness check",
    description="Returns a simple OK response indicating the API process is running.",
)
def health():
    """Lightweight liveness probe — no expensive checks."""
    return HealthResponse()


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    description=(
        "Checks whether required infrastructure and configuration are present. "
        "Does NOT make actual LLM or embedding API calls."
    ),
)
def readiness(db: Session = Depends(get_db)):
    """Check that required config is present without making external calls."""
    # Check DB Connection
    db_status = "not_configured"
    if os.environ.get("DATABASE_URL"):
        try:
            db.execute(text("SELECT 1"))
            db_status = "configured"
        except Exception as e:
            logger.error(f"Database readiness check failed: {e}")
            db_status = "error"

    embedding_model = os.environ.get("EMBEDDING_MODEL", "")
    llm_provider = os.environ.get("LLM_PROVIDER", "")
    llm_api_key = os.environ.get("LLM_API_KEY", "")

    embedding_status = "configured" if embedding_model else "not_configured"
    llm_status = (
        "configured" if (llm_provider and llm_api_key) else "not_configured"
    )

    overall = "ready" if all([db_status == "configured", embedding_status == "configured", llm_status == "configured"]) else "not_ready"

    return ReadinessResponse(
        status=overall,
        database=db_status,
        embedding_model=embedding_status,
        llm_provider=llm_status,
    )
