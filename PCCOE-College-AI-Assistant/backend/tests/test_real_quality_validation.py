"""
Tests for Step 8F — Real PCCOE Knowledge Population & Quality Validation.
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
import os

from app.models.document import Document, DocumentVersion, DocumentChunk
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
    with patch.object(EmbeddingService, 'generate_embedding') as m:
        # We will use simple vectors to control retrieval. 
        # By default we return a positive vector.
        m.return_value = [0.1] * 384
        yield m

@pytest.fixture
def mock_llm():
    with patch.object(LLMService, 'get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        # Mock LLM to return exactly what it saw in context to prove grounding without hallucination.
        mock_provider.generate.side_effect = lambda **kwargs: f"Answered from: {kwargs.get('context')}" if kwargs.get('context') else "I'm sorry, I don't have enough information in the college knowledge base to answer that question."
        mock_get_provider.return_value = mock_provider
        yield mock_provider

@pytest.fixture
def test_storage(tmpdir):
    test_storage_dir = str(tmpdir.mkdir("storage"))
    return LocalStorageService(base_dir=test_storage_dir)

def test_real_question_validation_and_outdated_data(db_session: Session, test_storage, mock_embedding, mock_llm):
    """
    Validates:
    - Real question retrieval bounds (No fake PCCOE facts).
    - Outdated information correctly archived upon new version publish.
    - Data quality preservation (categories, metadata).
    """
    ingestion_service = DocumentIngestionService(db_session, storage_service=test_storage)
    approval_service = ApprovalService(db_session)
    rag_service = RAGService(db_session)
    rag_service.search_service.threshold = -1.0

    from app.models.user import User
    from app.models.enums import RoleEnum
    
    admin = User(username="sysadmin", email="sysadmin@pccoe.edu.in", hashed_password="pw", role=RoleEnum.SUPER_ADMIN)
    db_session.add(admin)
    db_session.commit()

    # 1. Setup Department & Document (V1)
    dept = Department(name="Computer Engineering", short_code="COMP")
    db_session.add(dept)
    db_session.commit()

    doc = Document(
        title="Department Factsheet", 
        description="Official CE factsheet",
        category="Departments",
        department_id=dept.id, 
        source="https://pccoe.edu.in/comp",
        status=StatusEnum.DRAFT
    )
    db_session.add(doc)
    db_session.commit()
    
    ver1 = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.DRAFT)
    db_session.add(ver1)
    db_session.commit()

    # 2. Ingest V1 Data
    # Contains specific bounded facts.
    v1_content = b"HOD of Computer Engineering is Dr. John Doe. There are 5 clubs."
    ingestion_service.process_document_version(ver1.id, "facts_v1.txt", v1_content)
    
    # Fast track approval for V1
    approval_service.submit_for_review(ver1.id, current_user=admin, comment="Submit V1")
    approval_service.approve(ver1.id, current_user=admin, comment="Approve V1")
    approval_service.publish(ver1.id, current_user=admin, comment="Publish V1")

    # 3. Real Question Validation (V1)
    res_v1 = rag_service.ask("Who is the HOD?")
    assert len(res_v1.sources) == 1
    assert "Dr. John Doe" in res_v1.answer
    # Metadata preserved
    assert res_v1.sources[0].title == "Department Factsheet"
    assert res_v1.sources[0].department == "Computer Engineering"
    assert res_v1.sources[0].source == "https://pccoe.edu.in/comp"
    assert res_v1.sources[0].document_version_id == ver1.id

    # 4. Setup Document (V2) - Outdated Information check
    ver2 = DocumentVersion(document_id=doc.id, version_number=2, status=StatusEnum.DRAFT)
    db_session.add(ver2)
    db_session.commit()

    v2_content = b"HOD of Computer Engineering is Dr. Jane Smith. There are 10 clubs."
    ingestion_service.process_document_version(ver2.id, "facts_v2.txt", v2_content)

    approval_service.submit_for_review(ver2.id, current_user=admin, comment="Submit V2")
    approval_service.approve(ver2.id, current_user=admin, comment="Approve V2")
    approval_service.publish(ver2.id, current_user=admin, comment="Publish V2")

    db_session.refresh(ver1)
    db_session.refresh(ver2)

    # V1 should be archived, V2 should be published
    assert ver1.status == StatusEnum.ARCHIVED
    assert ver2.status == StatusEnum.PUBLISHED

    # 5. Outdated Information Retrieval Check
    res_v2 = rag_service.ask("Who is the HOD?")
    # Answer should ONLY contain V2 facts
    assert "Dr. Jane Smith" in res_v2.answer
    assert "Dr. John Doe" not in res_v2.answer
    assert res_v2.sources[0].document_version_id == ver2.id

    # 6. Unanswered Question (No-Answer) validation
    # If the user asks a question fundamentally completely outside of embeddings,
    # we simulate that pgvector returns no results within threshold.
    rag_service.search_service.threshold = 0.999
    with patch.object(EmbeddingService, 'generate_embedding', return_value=[-0.1] * 384): 
        # Opposing vector
        res_no_answer = rag_service.ask("What is the hostel fee?")
        assert len(res_no_answer.sources) == 0
        assert "I'm sorry, I don't have enough information" in res_no_answer.answer

