"""
Health API routes — GET /api/v1/health and /api/v1/health/ready

Basic liveness check and infrastructure readiness probe.
"""

import os
import logging
from fastapi import APIRouter

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
def readiness():
    """Check that required config is present without making external calls."""
    db_url = os.environ.get("DATABASE_URL", "")
    embedding_model = os.environ.get("EMBEDDING_MODEL", "")
    llm_provider = os.environ.get("LLM_PROVIDER", "")
    llm_api_key = os.environ.get("LLM_API_KEY", "")

    db_status = "configured" if db_url else "not_configured"
    embedding_status = "configured" if embedding_model else "not_configured"
    llm_status = (
        "configured" if (llm_provider and llm_api_key) else "not_configured"
    )

    overall = "ready" if all([db_url, embedding_model, llm_provider, llm_api_key]) else "not_ready"

    return ReadinessResponse(
        status=overall,
        database=db_status,
        embedding_model=embedding_status,
        llm_provider=llm_status,
    )
