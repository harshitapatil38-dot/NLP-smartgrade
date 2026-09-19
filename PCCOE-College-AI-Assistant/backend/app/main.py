"""
PCCOE Intelligent College Information Assistant — FastAPI Application
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

API_V1_PREFIX = os.environ.get("API_V1_PREFIX", "/api/v1")

app = FastAPI(
    title="PCCOE Intelligent College Information Assistant API",
    description=(
        "Backend API for the PCCOE College Information Chatbot. "
        "Provides RAG-based question answering grounded in official "
        "college documents and knowledge."
    ),
    version="0.6.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — configurable via CORS_ALLOWED_ORIGINS env var
# ---------------------------------------------------------------------------

_cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(chat.router, prefix=API_V1_PREFIX)
app.include_router(health.router, prefix=API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Root — convenience redirect / welcome
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"], summary="API welcome message")
def read_root():
    return {
        "message": "Welcome to the PCCOE College AI Assistant API",
        "docs": "/docs",
        "health": f"{API_V1_PREFIX}/health",
    }
