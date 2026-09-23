"""
Tests for Step 8A — Complete the RAG Pipeline.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
import os

from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.enums import StatusEnum
from app.services.rag_service import RAGService, RAGResult
from app.services.semantic_search_service import SemanticSearchService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

@pytest.fixture
def mock_embedding():
    # Helper to mock embedding generation
    with patch.object(EmbeddingService, 'generate_embedding', return_value=[0.1] * 384) as m:
        yield m

@pytest.fixture
def mock_llm():
    # Helper to mock LLM calls
    with patch.object(LLMService, 'get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Mocked LLM Answer"
        mock_get_provider.return_value = mock_provider
        yield mock_provider

@pytest.fixture
def test_data(db_session: Session):
    # Create documents with various statuses
    
    # 1. Published doc
    doc1 = Document(title="Published Info", status=StatusEnum.PUBLISHED)
    db_session.add(doc1)
    db_session.commit()
    ver1 = DocumentVersion(document_id=doc1.id, version_number=1, status=StatusEnum.PUBLISHED)
    db_session.add(ver1)
    db_session.commit()
    chunk1 = DocumentChunk(document_version_id=ver1.id, chunk_text="Library is open 9 AM to 5 PM.", chunk_order=1, embedding=[0.1] * 384)
    db_session.add(chunk1)
    
    # 2. Draft doc
    doc2 = Document(title="Draft Info", status=StatusEnum.DRAFT)
    db_session.add(doc2)
    db_session.commit()
    ver2 = DocumentVersion(document_id=doc2.id, version_number=1, status=StatusEnum.DRAFT)
    db_session.add(ver2)
    db_session.commit()
    chunk2 = DocumentChunk(document_version_id=ver2.id, chunk_text="Secret draft info.", chunk_order=1, embedding=[0.1] * 384)
    db_session.add(chunk2)
    
    # 3. Archived doc
    doc3 = Document(title="Archived Info", status=StatusEnum.ARCHIVED)
    db_session.add(doc3)
    db_session.commit()
    ver3 = DocumentVersion(document_id=doc3.id, version_number=1, status=StatusEnum.ARCHIVED)
    db_session.add(ver3)
    db_session.commit()
    chunk3 = DocumentChunk(document_version_id=ver3.id, chunk_text="Old library hours were 8 AM to 4 PM.", chunk_order=1, embedding=[0.1] * 384)
    db_session.add(chunk3)
    
    # 4. Pending Review doc
    doc4 = Document(title="Pending Info", status=StatusEnum.PENDING_REVIEW)
    db_session.add(doc4)
    db_session.commit()
    ver4 = DocumentVersion(document_id=doc4.id, version_number=1, status=StatusEnum.PENDING_REVIEW)
    db_session.add(ver4)
    db_session.commit()
    chunk4 = DocumentChunk(document_version_id=ver4.id, chunk_text="Pending library hours.", chunk_order=1, embedding=[0.1] * 384)
    db_session.add(chunk4)
    
    db_session.commit()
    return {"published": chunk1, "draft": chunk2, "archived": chunk3, "pending": chunk4}

def test_semantic_search_published_only(db_session: Session, test_data, mock_embedding):
    """3, 4, 5, 6: Only PUBLISHED knowledge is retrieved. Draft, Archived, Pending are excluded."""
    service = SemanticSearchService(db_session)
    # Mock max distance check so all are retrieved, but filter blocks non-published
    service.threshold = -0.5  # Cosine distance limit calculation -> 1.0 - (-0.5) = 1.5 distance
    
    results = service.search("Library hours")
    
    mock_embedding.assert_called_once_with("Library hours")
    
    assert len(results) == 1
    assert results[0]["chunk_id"] == test_data["published"].id
    assert "Secret draft info" not in results[0]["text"]
    assert "Old library hours" not in results[0]["text"]
    assert "Pending library hours" not in results[0]["text"]

def test_semantic_search_similarity_threshold(db_session: Session, test_data, mock_embedding):
    """10. Similarity threshold works."""
    service = SemanticSearchService(db_session)
    # Cosine distance between [0.1]*384 and [0.1]*384 is approx 0.0
    # Threshold 0.9 means max distance 0.1
    service.threshold = 0.9 
    results = service.search("Match")
    assert len(results) == 1

    # Now make the distance fail the threshold by mocking embedding mismatch
    # In pgvector distance between [0.1]*384 and [-0.1]*384 is 2.0 (opposite vectors)
    with patch.object(EmbeddingService, 'generate_embedding', return_value=[-0.1] * 384):
        service.threshold = 0.9  # max distance 0.1
        results = service.search("No Match")
        assert len(results) == 0

def test_rag_pipeline_end_to_end(db_session: Session, test_data, mock_embedding, mock_llm):
    """1, 2, 7, 8, 9: End to End test"""
    rag_service = RAGService(db_session)
    
    # We enforce a loose threshold to guarantee retrieval
    rag_service.search_service.threshold = -1.0
    
    result = rag_service.ask("What are library hours?")
    
    # Assert query embedding and search were invoked
    mock_embedding.assert_called_once_with("What are library hours?")
    
    # Assert context passed to LLM
    mock_llm.generate.assert_called_once()
    kwargs = mock_llm.generate.call_args[1]
    assert "Library is open 9 AM to 5 PM" in kwargs["context"]
    assert "What are library hours?" in kwargs["user_question"]
    assert "official PCCOE College Information Assistant" in kwargs["system_prompt"]
    
    # Assert Sources are returned
    assert len(result.sources) == 1
    assert result.sources[0].title == "Published Info"
    assert result.answer == "Mocked LLM Answer"
    assert result.retrieved_chunks == 1

def test_rag_pipeline_no_answer(db_session: Session, mock_embedding, mock_llm):
    """11. No relevant documents produces a controlled no-answer response."""
    rag_service = RAGService(db_session)
    
    result = rag_service.ask("What is the secret code?")
    
    assert len(result.sources) == 0
    assert "I'm sorry, I don't have enough information" in result.answer
    mock_llm.generate.assert_not_called()

def test_llm_failure_handling(db_session: Session, test_data, mock_embedding):
    """12. LLM failure is handled correctly."""
    from app.services.llm_service import LLMProviderError
    rag_service = RAGService(db_session)
    rag_service.search_service.threshold = -1.0

    with patch.object(LLMService, 'get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = LLMProviderError("LLM is down")
        mock_get_provider.return_value = mock_provider
        
        with pytest.raises(LLMProviderError):
            rag_service.ask("Test question")

def test_retrieval_failure_handling(db_session: Session, mock_embedding):
    """13. Retrieval failure is handled correctly."""
    rag_service = RAGService(db_session)
    
    # Force a database exception during search
    with patch.object(rag_service.search_service, 'search', side_effect=Exception("Database error")):
        with pytest.raises(Exception, match="Database error"):
            rag_service.ask("Test question")
