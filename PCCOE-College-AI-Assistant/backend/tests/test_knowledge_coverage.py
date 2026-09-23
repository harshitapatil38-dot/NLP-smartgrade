import pytest
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.enums import StatusEnum, ProcessingStatusEnum
from app.services.knowledge_service import KnowledgeService
from app.services.approval_service import ApprovalService
from app.services.semantic_search_service import SemanticSearchService
from app.services.rag_service import RAGService
from app.schemas.api import ChatRequest
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.ingestion.storage import LocalStorageService
from app.services.ingestion.file_validator import FileValidator
from bs4 import BeautifulSoup
import os

def mock_llm_response(prompt: str, **kwargs):
    if "clubs" in prompt.lower():
        return "PCCOE has various clubs including NSS, Art Circle, and Robotics."
    if "library" in prompt.lower():
        return "The Central Library has a rich collection of books and journals."
    if "facilities" in prompt.lower():
        return "PCCOE provides modern laboratories and sports facilities."
    if "scholarship" in prompt.lower():
        return "Various state and national scholarships are available."
    if "mars" in prompt.lower() or "not enough information" in prompt.lower():
        return "I'm sorry, I don't have enough information in the college knowledge base to answer that question."
    return "This is a grounded answer based on the PCCOE source."

@pytest.fixture
def mock_html_storage(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))
    return storage

@pytest.fixture
def test_user(db_session):
    from app.models.user import User
    from app.models.enums import RoleEnum
    user = User(
        username="testadmin",
        email="testadmin@pccoepune.org",
        hashed_password="fake",
        role=RoleEnum.ADMIN
    )
    db_session.add(user)
    db_session.commit()
    return user

def populate_test_documents(db_session, test_user, storage):
    validator = FileValidator(allowed_extensions=['html'], max_size_mb=10)
    ingestion = DocumentIngestionService(db_session, storage, validator)
    
    # Create DRAFT document
    doc_draft = Document(
        title="Clubs Info (DRAFT)",
        category="Clubs/student activities",
        source="https://www.pccoepune.com/pccoe-collegiate-clubs.php",
        status=StatusEnum.DRAFT,
        uploaded_by=test_user.id
    )
    db_session.add(doc_draft)
    db_session.commit()
    
    ver_draft = DocumentVersion(
        document_id=doc_draft.id,
        version_number=1,
        status=StatusEnum.DRAFT,
    )
    db_session.add(ver_draft)
    db_session.commit()
    
    html = b"<html><body>PCCOE has various clubs including NSS, Art Circle, and Robotics.</body></html>"
    file_path = storage.save_file("clubs.html", html)
    ver_draft.file_path = file_path
    db_session.commit()
    
    # Create PUBLISHED document
    doc_pub = Document(
        title="Library Info",
        category="Library",
        source="https://www.pccoepune.com/library.php",
        status=StatusEnum.PUBLISHED,
        uploaded_by=test_user.id
    )
    db_session.add(doc_pub)
    db_session.commit()
    
    ver_pub = DocumentVersion(
        document_id=doc_pub.id,
        version_number=1,
        status=StatusEnum.PUBLISHED,
    )
    db_session.add(ver_pub)
    db_session.commit()
    
    html2 = b"<html><body>The Central Library has a rich collection of books and journals.</body></html>"
    file_path2 = storage.save_file("library.html", html2)
    ver_pub.file_path = file_path2
    db_session.commit()
    
    # Process the published document to chunk and embed
    ingestion.process_document_version(ver_pub.id)
    
    # Create another PUBLISHED document (Facilities)
    doc_fac = Document(
        title="Facilities Info",
        category="Facilities",
        source="https://www.pccoepune.com/facilities.php",
        status=StatusEnum.PUBLISHED,
        uploaded_by=test_user.id
    )
    db_session.add(doc_fac)
    db_session.commit()
    
    ver_fac = DocumentVersion(
        document_id=doc_fac.id,
        version_number=1,
        status=StatusEnum.PUBLISHED,
    )
    db_session.add(ver_fac)
    db_session.commit()
    
    html_fac = b"<html><body>PCCOE provides modern laboratories and sports facilities.</body></html>"
    file_path_fac = storage.save_file("facilities.html", html_fac)
    ver_fac.file_path = file_path_fac
    db_session.commit()
    
    ingestion.process_document_version(ver_fac.id)
    
    # Create another PUBLISHED document (Scholarships)
    doc_sch = Document(
        title="Scholarship Info",
        category="Student services",
        source="https://www.pccoepune.com/scholarship-details.php",
        status=StatusEnum.PUBLISHED,
        uploaded_by=test_user.id
    )
    db_session.add(doc_sch)
    db_session.commit()
    
    ver_sch = DocumentVersion(
        document_id=doc_sch.id,
        version_number=1,
        status=StatusEnum.PUBLISHED,
    )
    db_session.add(ver_sch)
    db_session.commit()
    
    html_sch = b"<html><body>Various state and national scholarships are available.</body></html>"
    file_path_sch = storage.save_file("scholarships.html", html_sch)
    ver_sch.file_path = file_path_sch
    db_session.commit()
    
    ingestion.process_document_version(ver_sch.id)
    
    # Create ARCHIVED document
    doc_arch = Document(
        title="Old Info",
        category="College Information",
        source="https://www.pccoepune.com/",
        status=StatusEnum.ARCHIVED,
        uploaded_by=test_user.id
    )
    db_session.add(doc_arch)
    db_session.commit()
    
    ver_arch = DocumentVersion(
        document_id=doc_arch.id,
        version_number=1,
        status=StatusEnum.ARCHIVED,
    )
    db_session.add(ver_arch)
    db_session.commit()
    
    html3 = b"<html><body>Old PCCOE Information that is archived.</body></html>"
    file_path3 = storage.save_file("old.html", html3)
    ver_arch.file_path = file_path3
    db_session.commit()
    
    ingestion.process_document_version(ver_arch.id)
    
    return doc_draft, doc_pub, doc_arch

def test_knowledge_coverage_filters(db_session, test_user, mock_html_storage):
    populate_test_documents(db_session, test_user, mock_html_storage)
    
    search_service = SemanticSearchService(db_session)
    
    # Search for clubs -> should return empty because it's DRAFT
    results = search_service.search("What clubs are there?")
    
    # Even if similarity matches, we shouldn't get the DRAFT chunk
    draft_returned = any(r["source"] == "https://www.pccoepune.com/pccoe-collegiate-clubs.php" for r in results)
    assert not draft_returned
    
    # Search for old info -> should return empty because it's ARCHIVED
    results2 = search_service.search("Old PCCOE Information")
    arch_returned = any(r["source"] == "https://www.pccoepune.com/" for r in results2)
    assert not arch_returned
    
    # Search for library -> should return results because it's PUBLISHED
    results3 = search_service.search("What is in the library?")
    assert len(results3) > 0
    assert results3[0]["source"] == "https://www.pccoepune.com/library.php"
    assert "books and journals" in results3[0]["text"]
    assert "document_version_id" in results3[0]

def test_rag_coverage(db_session, test_user, mock_html_storage, monkeypatch):
    from app.services.llm_service import LLMService, BaseLLMProvider
    
    class MockProvider(BaseLLMProvider):
        def __init__(self):
            super().__init__(model="test", api_key="test")
        def generate(self, system_prompt: str, user_question: str, context: str, **kwargs) -> str:
            return mock_llm_response(user_question)
            
    monkeypatch.setattr(LLMService, "get_provider", lambda: MockProvider())
    
    populate_test_documents(db_session, test_user, mock_html_storage)
    
    rag = RAGService(db_session)
    
    # Supported Question
    req = ChatRequest(question="Tell me about the library", session_id="test1234")
    resp = rag.ask(req.question)
    
    assert resp.answer == "The Central Library has a rich collection of books and journals."
    assert len(resp.sources) > 0
    assert resp.sources[0].source == "https://www.pccoepune.com/library.php"
    
    # Supported Question 2 (Facilities)
    req2 = ChatRequest(question="What facilities are available?", session_id="test1234")
    resp2 = rag.ask(req2.question)
    assert resp2.answer == "PCCOE provides modern laboratories and sports facilities."
    assert len(resp2.sources) > 0
    assert resp2.sources[0].source == "https://www.pccoepune.com/facilities.php"
    
    # Supported Question 3 (Scholarships)
    req3 = ChatRequest(question="Tell me about scholarships.", session_id="test1234")
    resp3 = rag.ask(req3.question)
    assert resp3.answer == "Various state and national scholarships are available."
    assert len(resp3.sources) > 0
    assert resp3.sources[0].source == "https://www.pccoepune.com/scholarship-details.php"
    
    # Unsupported Question (No-answer validation)
    req_unsupported = ChatRequest(question="What is the distance to Mars?", session_id="test1234")
    resp_unsupported = rag.ask(req_unsupported.question)
    
    assert "I don't have enough information" in resp_unsupported.answer
    assert len(resp_unsupported.sources) == 0

def test_admin_approval_workflow_safety(db_session, test_user, mock_html_storage):
    """
    Test that the admin workflow safely transitions the document,
    and it is not searchable until published.
    """
    import os
    
    # Mock file in storage
    html = b"<html><body>New approved content</body></html>"
    file_path = mock_html_storage.save_file("new.html", html)
    
    # DRAFT
    doc = Document(
        title="New Info",
        source="https://www.pccoepune.com/new",
        status=StatusEnum.DRAFT,
        uploaded_by=test_user.id
    )
    db_session.add(doc)
    db_session.commit()
    
    ver = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.DRAFT, file_path=file_path)
    db_session.add(ver)
    db_session.commit()
    
    approval_svc = ApprovalService(db_session)
    search_svc = SemanticSearchService(db_session)
    
    # DRAFT should not be searchable
    res1 = search_svc.search("New approved content")
    assert not any(r["source"] == "https://www.pccoepune.com/new" for r in res1)
    
    # PENDING_REVIEW
    approval_svc.submit_for_review(ver.id, test_user)
    res2 = search_svc.search("New approved content")
    assert not any(r["source"] == "https://www.pccoepune.com/new" for r in res2)
    
    # APPROVED
    # Need another user for approval since you can't approve your own submission
    from app.models.user import User
    from app.models.enums import RoleEnum
    approver = User(username="approver", email="approver@pccoepune.org", hashed_password="fake", role=RoleEnum.ADMIN)
    db_session.add(approver)
    db_session.commit()
    approval_svc.approve(ver.id, approver, "Looks good")
    res3 = search_svc.search("New approved content")
    assert not any(r["source"] == "https://www.pccoepune.com/new" for r in res3)
    
    # PUBLISHED
    # For testing, we need to process it first so chunks exist
    validator = FileValidator(allowed_extensions=['html'], max_size_mb=10)
    ingestion = DocumentIngestionService(db_session, mock_html_storage, validator)
    ingestion.process_document_version(ver.id)
    
    # Now publish
    from app.services.knowledge_service import KnowledgeService
    ks = KnowledgeService(db_session)
    ks.publish_document_version(ver.id)
    
    # NOW it should be searchable
    res4 = search_svc.search("New approved content")
    assert any(r["source"] == "https://www.pccoepune.com/new" for r in res4)

def test_version_handling(db_session, test_user, mock_html_storage):
    validator = FileValidator(allowed_extensions=['html'], max_size_mb=10)
    ingestion = DocumentIngestionService(db_session, mock_html_storage, validator)
    ks = KnowledgeService(db_session)
    
    # Initial Doc + V1 Published
    doc = Document(
        title="Version Test",
        source="https://www.pccoepune.com/version",
        status=StatusEnum.PUBLISHED,
        uploaded_by=test_user.id
    )
    db_session.add(doc)
    db_session.commit()
    
    file_path1 = mock_html_storage.save_file("v1.html", b"<html><body>V1 CONTENT</body></html>")
    ver1 = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.PUBLISHED, file_path=file_path1)
    db_session.add(ver1)
    db_session.commit()
    ingestion.process_document_version(ver1.id)
    
    search_svc = SemanticSearchService(db_session)
    res_v1 = search_svc.search("V1 CONTENT")
    assert any("V1 CONTENT" in r["text"] for r in res_v1)
    
    # Now create V2, approve and publish
    file_path2 = mock_html_storage.save_file("v2.html", b"<html><body>V2 CONTENT SUPERSEDES V1</body></html>")
    ver2 = DocumentVersion(document_id=doc.id, version_number=2, status=StatusEnum.APPROVED, file_path=file_path2)
    db_session.add(ver2)
    db_session.commit()
    ingestion.process_document_version(ver2.id)
    
    # Publish V2
    ks.publish_document_version(ver2.id)
    
    db_session.refresh(ver1)
    assert ver1.status == StatusEnum.ARCHIVED
    
    # V1 should NOT be returned
    res_after_v2 = search_svc.search("V1 CONTENT")
    assert not any("V1 CONTENT" in r["text"] for r in res_after_v2)
    
    # V2 SHOULD be returned
    res_v2 = search_svc.search("V2 CONTENT")
    assert any("V2 CONTENT" in r["text"] for r in res_v2)

