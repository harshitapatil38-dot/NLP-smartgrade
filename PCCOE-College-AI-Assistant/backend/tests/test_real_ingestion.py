"""
Tests for Step 8E — Real PCCOE Knowledge Base Ingestion & Validation.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
import os

from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.approval import ApprovalRecord
from app.models.department import Department
from app.models.enums import StatusEnum, ProcessingStatusEnum
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.ingestion.storage import LocalStorageService
from app.services.approval_service import ApprovalService
from app.services.rag_service import RAGService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

@pytest.fixture
def mock_embedding():
    with patch.object(EmbeddingService, 'generate_embedding', return_value=[0.1] * 384) as m:
        yield m

@pytest.fixture
def mock_llm():
    with patch.object(LLMService, 'get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        # By default we want to simulate an LLM that replies with the context it was given
        mock_provider.generate.side_effect = lambda **kwargs: f"Based on knowledge: {kwargs.get('context')}" if kwargs.get('context') else "I'm sorry, I don't have enough information in the college knowledge base to answer that question."
        mock_get_provider.return_value = mock_provider
        yield mock_provider

@pytest.fixture
def test_storage(tmpdir):
    test_storage_dir = str(tmpdir.mkdir("storage"))
    return LocalStorageService(base_dir=test_storage_dir)

def test_admin_workflow_and_rag_grounding(db_session: Session, test_storage, mock_embedding, mock_llm):
    """
    Validates:
    - Admin workflow (Draft -> Submit -> Approve -> Publish -> Processing)
    - Metadata propagation (title, department, etc)
    - RAG real-data validation (grounding and retrieval)
    - No-hallucination behavior
    """
    ingestion_service = DocumentIngestionService(db_session, storage_service=test_storage)
    approval_service = ApprovalService(db_session)
    rag_service = RAGService(db_session)
    rag_service.search_service.threshold = -1.0 # Guarantee retrieval if any published chunks exist

    # 1. Admin creates document (DRAFT)
    dept = Department(name="Admissions", short_code="ADM")
    db_session.add(dept)
    db_session.commit()

    doc = Document(title="Admission Process Guidelines", department_id=dept.id, status=StatusEnum.DRAFT)
    db_session.add(doc)
    db_session.commit()
    
    ver = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.DRAFT)
    db_session.add(ver)
    db_session.commit()

    # 2. Upload file & process (Chunks generated)
    file_content = b"The admission process requires a 10th grade mark sheet and a valid ID proof."
    filename = "admissions.txt"
    processed_version = ingestion_service.process_document_version(ver.id, filename, file_content)
    
    assert processed_version.processing_status == ProcessingStatusEnum.COMPLETED
    assert processed_version.status == StatusEnum.DRAFT

    # 2b. Setup Users for Approval workflow
    from app.models.user import User
    from app.models.enums import RoleEnum
    
    submitter = User(username="submitter", email="submitter@pccoe.edu.in", hashed_password="pw", role=RoleEnum.STAFF)
    reviewer = User(username="admin", email="admin@pccoe.edu.in", hashed_password="pw", role=RoleEnum.ADMIN)
    db_session.add(submitter)
    db_session.add(reviewer)
    db_session.commit()

    # At this point, the document is DRAFT. 
    # Verify it is NOT searchable.
    result_draft = rag_service.ask("What is the admission process?")
    assert len(result_draft.sources) == 0
    assert "I don't have enough information" in result_draft.answer

    # 3. Submit for review (PENDING_REVIEW)
    approval_service.submit_for_review(ver.id, current_user=submitter, comment="Ready for review")
    db_session.refresh(processed_version)
    assert processed_version.status == StatusEnum.PENDING_REVIEW
    
    # Still not searchable
    result_pending = rag_service.ask("What is the admission process?")
    assert len(result_pending.sources) == 0

    # 4. Approve and Publish (PUBLISHED)
    approval_service.approve(ver.id, current_user=reviewer, comment="Approved")
    approval_service.publish(ver.id, current_user=reviewer, comment="Published")
    
    db_session.refresh(processed_version)
    assert processed_version.status == StatusEnum.PUBLISHED
    
    db_session.refresh(doc)
    assert doc.status == StatusEnum.PUBLISHED

    # 5. Semantic Search available -> Chatbot retrieves published knowledge
    # Real-world scenario: "What is the admission process?"
    result_published = rag_service.ask("What is the admission process?")
    
    # Verify Source Grounding
    assert len(result_published.sources) == 1
    assert result_published.sources[0].title == "Admission Process Guidelines"
    assert result_published.sources[0].department == "Admissions"
    # Document info was injected into LLM
    assert "10th grade mark sheet" in result_published.answer

    # 6. No-Hallucination validation
    # "Question not supported by the knowledge base -> no relevant retrieval -> no fabricated answer"
    # We simulate this by making the search threshold very strict or simulating no matches.
    # In pgvector, we can mock embedding to return a diametrically opposed vector or just adjust threshold.
    rag_service.search_service.threshold = 0.999 # Strict
    with patch.object(EmbeddingService, 'generate_embedding', return_value=[-0.1] * 384): # Opposite vector
        result_hallucination = rag_service.ask("Who is the HOD?")
        assert len(result_hallucination.sources) == 0
        assert "I'm sorry, I don't have enough information in the college knowledge base to answer that question." in result_hallucination.answer
        
    # 7. Idempotent reprocessing (republishing shouldn't duplicate chunks)
    original_chunks = db_session.query(DocumentChunk).filter_by(document_version_id=ver.id).count()
    ingestion_service.process_document_version(ver.id, filename, file_content)
    assert db_session.query(DocumentChunk).filter_by(document_version_id=ver.id).count() == original_chunks
