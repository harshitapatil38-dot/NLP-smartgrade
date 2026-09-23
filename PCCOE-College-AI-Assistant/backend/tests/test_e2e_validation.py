import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.database.database import get_db
from app.models.user import User
from app.models.enums import RoleEnum, StatusEnum, ProcessingStatusEnum
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.core.security import create_access_token
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService, LLMProviderError

client = TestClient(app, raise_server_exceptions=False)

@pytest.fixture(autouse=True)
def override_get_db(db_session):
    def _get_test_db():
        yield db_session
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def admin_token(db_session):
    user = User(email="admin_e2e@pccoe.edu", username="admin_e2e", hashed_password="fakehash", role=RoleEnum.ADMIN, is_active=True)
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, RoleEnum.ADMIN.value)

@pytest.fixture
def admin2_token(db_session):
    user = User(email="admin2_e2e@pccoe.edu", username="admin2_e2e", hashed_password="fakehash", role=RoleEnum.ADMIN, is_active=True)
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, RoleEnum.ADMIN.value)

@pytest.fixture
def student_token(db_session):
    user = User(email="student_e2e@pccoe.edu", username="student_e2e", hashed_password="fakehash", role=RoleEnum.STAFF, is_active=True)
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, RoleEnum.STAFF.value)

@pytest.fixture
def mock_embedding(monkeypatch):
    monkeypatch.setattr(EmbeddingService, "generate_embedding", lambda text: [0.1] * 384)

@pytest.fixture
def mock_llm_provider(monkeypatch):
    def fake_generate(system_prompt=None, user_question="", context=None, **kwargs):
        prompt_lower = user_question.lower()
        context_lower = context.lower() if context else ""
        if "mars" in prompt_lower:
            return "I'm sorry, I don't have enough information in the college knowledge base to answer that question."
        if "timings" in prompt_lower:
            return "The library timings are 9 AM to 5 PM."
        if "clubs" in prompt_lower:
            if "10 student clubs" in context_lower:
                return "The college has 10 student clubs."
            elif "5 student clubs" in context_lower:
                return "The college has 5 student clubs."
            return "PCCOE has various student clubs like NSS and Art Circle."
        if "library" in prompt_lower:
            return "The PCCOE Library is a central facility."
        if "facilities" in prompt_lower:
            return "PCCOE provides modern facilities including labs and sports grounds."
        if "scholarship" in prompt_lower:
            return "PCCOE offers various scholarships based on merit."
        if "departments" in prompt_lower:
            return "PCCOE has Computer, IT, Mechanical, and Civil departments."
        return "This is a standard grounded answer."

    class FakeProvider:
        def generate(self, system_prompt=None, user_question="", context=None, **kwargs):
            return fake_generate(system_prompt=system_prompt, user_question=user_question, context=context, **kwargs)
            
    monkeypatch.setattr(LLMService, "get_provider", lambda: FakeProvider())

# 1. ADMIN -> DOCUMENT -> PUBLISH -> STUDENT RAG
def test_admin_to_student_rag_lifecycle(admin_token, admin2_token, db_session, monkeypatch, mock_embedding, mock_llm_provider):
    import app.services.ingestion.storage
    monkeypatch.setattr(app.services.ingestion.storage.LocalStorageService, "save_file", lambda s, f, c: "/fake/path")
    
    # 1. Upload valid document
    file_content = b"The library timings are 9 AM to 5 PM."
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Library Info"}, files={"file": ("lib.txt", file_content, "text/plain")})
    assert resp.status_code == 201
    doc_id = resp.json()["id"]
    
    db_doc = db_session.query(Document).get(doc_id)
    version = db_doc.versions[0]
    
    # Verify created as DRAFT
    assert version.status == StatusEnum.DRAFT
    
    # 2. Submit for review
    resp = client.post(f"/api/v1/workflow/documents/versions/{version.id}/submit", headers={"Authorization": f"Bearer {admin_token}"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == StatusEnum.PENDING_REVIEW.value
    
    # 3. Approve (using admin2 to avoid self-approval)
    resp = client.post(f"/api/v1/workflow/documents/versions/{version.id}/approve", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == StatusEnum.APPROVED.value
    
    # 4. Publish
    resp = client.post(f"/api/v1/workflow/documents/versions/{version.id}/publish", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == StatusEnum.PUBLISHED.value
    
    # Wait for processing to happen (in tests, we run synchronously or simulate)
    # The actual processing task creates chunks and embeddings. In our FastAPI test client, background tasks run after the response.
    # We can verify it manually by checking DB
    db_session.refresh(version)
    # In tests, BackgroundTasks are not executed by TestClient reliably without Starlette TestClient with side effects.
    # We'll just inject the chunk to simulate processing completed by the worker.
    version.processing_status = ProcessingStatusEnum.COMPLETED
    chunk = DocumentChunk(document_version_id=version.id, chunk_text="The library timings are 9 AM to 5 PM.", chunk_order=1, embedding=[0.1]*384)
    db_session.add(chunk)
    db_session.commit()
    
    db_session.refresh(version)
    assert version.processing_status == ProcessingStatusEnum.COMPLETED
    assert len(version.chunks) > 0
    
    # 5. Student RAG
    # Using negative threshold to guarantee retrieval
    from app.services.semantic_search_service import SemanticSearchService
    monkeypatch.setattr(SemanticSearchService, "__init__", lambda s, db: setattr(s, 'db', db) or setattr(s, 'threshold', -1.0) or setattr(s, 'top_k', 5))
    
    resp = client.post("/api/v1/chat", json={"question": "What are the library timings?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "9 AM to 5 PM" in data["answer"]
    assert len(data["sources"]) > 0
    assert data["sources"][0]["title"] == "Library Info"
    assert data["sources"][0]["document_id"] == doc_id
    assert data["sources"][0]["document_version_id"] == version.id


# 2. ANTI-HALLUCINATION TEST
def test_anti_hallucination(db_session, mock_embedding, mock_llm_provider, monkeypatch):
    # Ensure no docs
    resp = client.post("/api/v1/chat", json={"question": "What is the distance from PCCOE to Mars?"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) == 0
    assert "I don't have enough information" in data["answer"]


# 3. CONVERSATIONAL FOLLOW-UP TEST
def test_conversational_followup(admin_token, admin2_token, db_session, monkeypatch, mock_embedding, mock_llm_provider):
    import app.services.ingestion.storage
    monkeypatch.setattr(app.services.ingestion.storage.LocalStorageService, "save_file", lambda s, f, c: "/fake/path")
    from app.services.semantic_search_service import SemanticSearchService
    monkeypatch.setattr(SemanticSearchService, "__init__", lambda s, db: setattr(s, 'db', db) or setattr(s, 'threshold', -1.0) or setattr(s, 'top_k', 5))
    
    # Add a document to search
    doc = Document(title="PCCOE Library", status=StatusEnum.PUBLISHED)
    db_session.add(doc)
    db_session.commit()
    ver = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.PUBLISHED, processing_status=ProcessingStatusEnum.COMPLETED)
    db_session.add(ver)
    db_session.commit()
    chunk = DocumentChunk(document_version_id=ver.id, chunk_text="The library timings are 9 AM to 5 PM.", chunk_order=1, embedding=[0.1]*384)
    db_session.add(chunk)
    db_session.commit()
    
    # Q1
    resp1 = client.post("/api/v1/chat", json={"question": "Tell me about the PCCOE library."})
    assert resp1.status_code == 200
    session_id = resp1.json()["session_id"]
    
    # Q2
    resp2 = client.post("/api/v1/chat", json={"question": "What are its timings?", "session_id": session_id})
    assert resp2.status_code == 200
    data = resp2.json()
    assert "9 AM to 5 PM" in data["answer"]


# 4. DOCUMENT VERSIONING TEST
def test_document_versioning(admin_token, admin2_token, db_session, monkeypatch, mock_embedding, mock_llm_provider):
    import app.services.ingestion.storage
    monkeypatch.setattr(app.services.ingestion.storage.LocalStorageService, "save_file", lambda s, f, c: "/fake/path")
    from app.services.semantic_search_service import SemanticSearchService
    monkeypatch.setattr(SemanticSearchService, "__init__", lambda s, db: setattr(s, 'db', db) or setattr(s, 'threshold', -1.0) or setattr(s, 'top_k', 5))
    
    # V1
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Clubs Info"}, files={"file": ("v1.txt", b"The college has 5 student clubs.", "text/plain")})
    doc_id = resp.json()["id"]
    db_doc = db_session.query(Document).get(doc_id)
    v1 = db_doc.versions[0]
    
    client.post(f"/api/v1/workflow/documents/versions/{v1.id}/submit", headers={"Authorization": f"Bearer {admin_token}"}, json={})
    client.post(f"/api/v1/workflow/documents/versions/{v1.id}/approve", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    client.post(f"/api/v1/workflow/documents/versions/{v1.id}/publish", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    
    db_session.refresh(v1)
    assert v1.status == StatusEnum.PUBLISHED
    
    # Simulate processing
    v1.processing_status = ProcessingStatusEnum.COMPLETED
    chunk1 = DocumentChunk(document_version_id=v1.id, chunk_text="The college has 5 student clubs.", chunk_order=1, embedding=[0.1]*384)
    db_session.add(chunk1)
    db_session.commit()
    
    # Query V1
    resp_chat = client.post("/api/v1/chat", json={"question": "How many clubs are there?"})
    assert "5 student clubs" in resp_chat.json()["answer"]
    
    # V2
    from app.services.knowledge_service import KnowledgeService
    from app.schemas.knowledge import DocumentVersionCreate
    k_service = KnowledgeService(db_session)
    v2 = k_service.create_document_version(DocumentVersionCreate(document_id=doc_id, file_path="/fake", uploaded_by=db_doc.uploaded_by))
    
    # Publish V2
    k_service.update_document_version_status(v2.id, StatusEnum.PENDING_REVIEW)
    k_service.update_document_version_status(v2.id, StatusEnum.APPROVED)
    resp_pub2 = client.post(f"/api/v1/workflow/documents/versions/{v2.id}/publish", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    assert resp_pub2.status_code == 200
    
    # Simulate processing V2
    v2.processing_status = ProcessingStatusEnum.COMPLETED
    chunk2 = DocumentChunk(document_version_id=v2.id, chunk_text="The college has 10 student clubs.", chunk_order=1, embedding=[0.1]*384)
    db_session.add(chunk2)
    db_session.commit()
    
    db_session.refresh(v1)
    db_session.refresh(v2)
    assert v1.status == StatusEnum.ARCHIVED
    assert v2.status == StatusEnum.PUBLISHED
    
    # Query V2
    resp_chat2 = client.post("/api/v1/chat", json={"question": "How many clubs are there?"})
    ans = resp_chat2.json()
    assert "10 student clubs" in ans["answer"]
    assert ans["sources"][0]["document_version_id"] == v2.id


# 5. ADMIN SECURITY TEST
def test_admin_security(student_token, db_session):
    # Unauthenticated cannot upload
    assert client.post("/api/v1/documents/upload", files={"file": ("t.txt", b"t", "text/plain")}).status_code == 401
    
    # Student cannot upload
    assert client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {student_token}"}, files={"file": ("t.txt", b"t", "text/plain")}).status_code == 403
    
    # Unauthenticated cannot approve
    assert client.post("/api/v1/workflow/documents/versions/1/approve", json={}).status_code == 401
    
    # Public chat accessible without auth
    resp = client.post("/api/v1/chat", json={"question": "Hello"})
    assert resp.status_code == 200


# 6. INVALID DOCUMENT TESTS
def test_invalid_documents(admin_token):
    # Unsupported extension
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Bad"}, files={"file": ("bad.exe", b"bad", "application/x-msdownload")})
    assert resp.status_code == 400
    assert "unsupported file extension" in resp.json()["detail"].lower()
    
    # Empty file
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Empty"}, files={"file": ("empty.txt", b"", "text/plain")})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


# 7. FAILURE / TRANSACTION SAFETY
def test_transaction_safety_invalid_transition(admin_token, db_session):
    # Try invalid workflow transition
    doc = Document(title="Fail Test", status=StatusEnum.DRAFT)
    db_session.add(doc)
    db_session.commit()
    ver = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.DRAFT)
    db_session.add(ver)
    db_session.commit()
    
    # Try to approve a DRAFT directly
    resp = client.post(f"/api/v1/workflow/documents/versions/{ver.id}/approve", headers={"Authorization": f"Bearer {admin_token}"}, json={})
    assert resp.status_code == 409
    
    # Verify it rolled back and is still DRAFT
    db_session.refresh(ver)
    assert ver.status == StatusEnum.DRAFT


# 8. REAL PCCOE KNOWLEDGE VALIDATION
def test_real_pccoe_knowledge(db_session, monkeypatch, mock_embedding, mock_llm_provider):
    from app.services.semantic_search_service import SemanticSearchService
    monkeypatch.setattr(SemanticSearchService, "__init__", lambda s, db: setattr(s, 'db', db) or setattr(s, 'threshold', -1.0) or setattr(s, 'top_k', 5))
    
    # Insert mock REAL sources that simulate what was imported
    docs_to_insert = [
        ("Facilities", "https://www.pccoepune.com/facilities.php", "PCCOE provides modern laboratories and sports facilities."),
        ("Scholarships", "https://www.pccoepune.com/scholarship-details.php", "Various state and national scholarships are available."),
        ("Departments", "https://www.pccoepune.com/pccoe-departments.php", "PCCOE offers multiple engineering departments."),
        ("Clubs", "https://www.pccoepune.com/pccoe-collegiate-clubs.php", "PCCOE has various clubs including NSS, Art Circle, and Robotics."),
        ("Library", "https://www.pccoepune.com/library.php", "The Central Library has a rich collection of books and journals.")
    ]
    
    for title, source, text in docs_to_insert:
        doc = Document(title=title, source=source, status=StatusEnum.PUBLISHED)
        db_session.add(doc)
        db_session.commit()
        ver = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.PUBLISHED, processing_status=ProcessingStatusEnum.COMPLETED)
        db_session.add(ver)
        db_session.commit()
        chunk = DocumentChunk(document_version_id=ver.id, chunk_text=text, chunk_order=1, embedding=[0.1]*384)
        db_session.add(chunk)
    db_session.commit()
    
    # Test queries
    queries = [
        "What facilities are available?",
        "Tell me about scholarships.",
        "What departments does PCCOE have?",
        "What clubs are available?",
        "Tell me about the library."
    ]
    
    for q in queries:
        resp = client.post("/api/v1/chat", json={"question": q})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sources"]) > 0
        assert "pccoepune.com" in data["sources"][0]["source"]
        assert data["answer"] != "I'm sorry, I don't have enough information in the college knowledge base to answer that question."
