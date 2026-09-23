"""
Tests for Step 8B — Production Chat API
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy.orm import Session

from app.main import app
from app.services.rag_service import RAGService, RAGResult
from app.services.context_builder import SourceReference
from app.services.llm_service import LLMProviderError

@pytest.fixture
def client(db_session: Session):
    from app.database.database import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    # raise_server_exceptions=False is required so TestClient doesn't bypass 500 handlers
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()

def test_chat_valid_question(client: TestClient):
    """1, 5, 6, 7. Valid question returns 200. RAGService is called and answer/sources returned."""
    mock_result = RAGResult(
        answer="The library is open 9 to 5.",
        sources=[
            SourceReference(
                document_id=1,
                document_version_id=1,
                chunk_id=1,
                title="Library Guide",
                source="website",
                page_number=1,
                similarity_score=0.9,
                department="Library"
            )
        ],
        query="Library hours",
        retrieved_chunks=1,
        context_truncated=False
    )
    
    with patch.object(RAGService, 'ask', return_value=mock_result) as mock_ask:
        response = client.post("/api/v1/chat", json={"question": "What are the library hours?"})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "The library is open 9 to 5."
        assert len(data["sources"]) == 1
        assert data["sources"][0]["title"] == "Library Guide"
        mock_ask.assert_called_once()
        # Verify no auth was required
        assert "session_id" in data

def test_chat_empty_question(client: TestClient):
    """2. Empty question is rejected."""
    response = client.post("/api/v1/chat", json={"question": ""})
    assert response.status_code == 400 # Pydantic validation RequestValidationError -> 400

def test_chat_whitespace_question(client: TestClient):
    """3. Whitespace-only question is rejected."""
    response = client.post("/api/v1/chat", json={"question": "   "})
    assert response.status_code == 400
    # Custom HTTPException raises {"detail": "Question cannot be empty."}
    assert "Question cannot be empty" in response.json()["detail"]

def test_chat_long_question(client: TestClient):
    """4. Long/invalid question is rejected according to validation rules."""
    long_question = "a" * 2001
    response = client.post("/api/v1/chat", json={"question": long_question})
    assert response.status_code == 400 # Pydantic validation RequestValidationError -> 400

def test_chat_no_answer_behavior(client: TestClient):
    """8. No-answer response is preserved."""
    mock_result = RAGResult(
        answer="I'm sorry, I don't have enough information in the college knowledge base to answer that question.",
        sources=[],
        query="Secret",
        retrieved_chunks=0,
        context_truncated=False
    )
    
    with patch.object(RAGService, 'ask', return_value=mock_result):
        response = client.post("/api/v1/chat", json={"question": "Tell me a secret."})
        assert response.status_code == 200
        data = response.json()
        assert "I don't have enough information" in data["answer"]
        assert len(data["sources"]) == 0

def test_chat_llm_failure(client: TestClient):
    """10. LLM failure is handled safely. 11. No secrets exposed."""
    with patch.object(RAGService, 'ask', side_effect=LLMProviderError("LLM is down")):
        response = client.post("/api/v1/chat", json={"question": "What are the library hours?"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "LLM_SERVICE_ERROR"
        assert "LLM is down" not in response.json()["error"]["message"] # Safety check for secrets

def test_chat_retrieval_failure(client: TestClient):
    """9. Retrieval failure is handled safely. 11. No secrets exposed."""
    with patch.object(RAGService, 'ask', side_effect=Exception("Database connection lost")):
        response = client.post("/api/v1/chat", json={"question": "What are the library hours?"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "Database connection lost" not in response.json()["error"]["message"]

def test_chat_auth_behavior_preserved(client: TestClient):
    """12. Existing authentication behavior is preserved (public endpoint)."""
    # Simply hitting it without headers works.
    with patch.object(RAGService, 'ask', return_value=RAGResult(
        answer="Yes", 
        sources=[], 
        query="Is this public?", 
        retrieved_chunks=0, 
        context_truncated=False
    )):
        response = client.post("/api/v1/chat", json={"question": "Is this public?"})
        assert response.status_code == 200
