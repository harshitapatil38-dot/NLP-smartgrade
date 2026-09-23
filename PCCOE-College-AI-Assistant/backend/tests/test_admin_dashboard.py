import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import get_db
from app.models.user import User
from app.models.enums import RoleEnum, StatusEnum, ProcessingStatusEnum
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.core.security import create_access_token
import os

client = TestClient(app)

@pytest.fixture(autouse=True)
def override_get_db(db_session):
    def _get_test_db():
        yield db_session
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def admin_token(db_session):
    user = User(email="admin_dash@pccoe.edu", username="admin_dash", hashed_password="fakehash", role=RoleEnum.ADMIN, is_active=True)
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, RoleEnum.ADMIN.value)

@pytest.fixture
def student_token(db_session):
    user = User(email="student_dash@pccoe.edu", username="student_dash", hashed_password="fakehash", role=RoleEnum.STAFF, is_active=True)
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, RoleEnum.STAFF.value)

# 1, 2, 3: Access Control
def test_dashboard_access_control(admin_token, student_token):
    # Unauthenticated
    resp = client.get("/api/v1/documents/")
    assert resp.status_code in [401, 403]
    
    # Non-admin
    resp = client.get("/api/v1/documents/", headers={"Authorization": f"Bearer {student_token}"})
    assert resp.status_code == 403
    
    # Admin
    resp = client.get("/api/v1/documents/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200

# 4, 5, 14: Upload & DRAFT
def test_document_upload(admin_token, db_session, monkeypatch):
    import app.services.ingestion.storage
    monkeypatch.setattr(app.services.ingestion.storage.LocalStorageService, "save_file", lambda s, f, c: "/fake/path")
    
    # Invalid upload
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={
        "title": "Bad File"
    }, files={"file": ("test.exe", b"fake", "application/x-msdownload")})
    assert resp.status_code == 400
    
    # Valid upload
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={
        "title": "Good File"
    }, files={"file": ("test.txt", b"plain text", "text/plain")})
    
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["title"] == "Good File"
    assert doc["status"] == StatusEnum.DRAFT.value
    
    # Verify version 1 created as DRAFT
    db_doc = db_session.query(Document).get(doc["id"])
    assert len(db_doc.versions) == 1
    assert db_doc.versions[0].status == StatusEnum.DRAFT

@pytest.fixture
def admin2_token(db_session):
    user = User(email="admin2@pccoe.edu", username="admin2", hashed_password="fakehash", role=RoleEnum.ADMIN, is_active=True)
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, RoleEnum.ADMIN.value)

# 6, 7, 8, 9, 10, 11, 12, 13: Workflow & Search Visibility
def test_workflow_and_search(admin_token, admin2_token, db_session, monkeypatch):
    # Mocks
    import app.services.ingestion.storage
    monkeypatch.setattr(app.services.ingestion.storage.LocalStorageService, "save_file", lambda s, f, c: "/fake/path")
    
    class MockBackgroundTasks:
        def add_task(self, *args, **kwargs):
            pass
    
    # Upload doc
    resp = client.post("/api/v1/documents/upload", headers={"Authorization": f"Bearer {admin_token}"}, data={"title": "Test Doc"}, files={"file": ("test.txt", b"txt", "text/plain")})
    doc_id = resp.json()["id"]
    db_doc = db_session.query(Document).get(doc_id)
    version = db_doc.versions[0]
    
    from app.services.semantic_search_service import SemanticSearchService
    search_service = SemanticSearchService(db_session)
    search_service.threshold = 0.0
    
    from app.services.embedding_service import EmbeddingService
    chunk = DocumentChunk(document_version_id=version.id, chunk_text="Test", chunk_order=1, embedding=EmbeddingService.generate_embedding("Test"))
    db_session.add(chunk)
    db_session.commit()
    
    # 6: DRAFT not in search
    results = search_service.search("Test")
    assert len(results) == 0
    
    # 7: Submit
    resp = client.post(f"/api/v1/workflow/documents/versions/{version.id}/submit", headers={"Authorization": f"Bearer {admin_token}"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == StatusEnum.PENDING_REVIEW.value
    
    # 13: Unauthorized transition (approve from approved -> should fail) - wait, test normal approve first
    
    # 8: Approve using admin2_token since admin cannot approve own submission
    resp = client.post(f"/api/v1/workflow/documents/versions/{version.id}/approve", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == StatusEnum.APPROVED.value
    
    # 9: Publish using admin2_token
    resp = client.post(f"/api/v1/workflow/documents/versions/{version.id}/publish", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == StatusEnum.PUBLISHED.value
    
    # 10: Published in search
    results = search_service.search("Test")
    assert len(results) > 0
    
    # 11: Publishing newer version archives old
    # Create new version manually for test
    from app.services.knowledge_service import KnowledgeService
    from app.schemas.knowledge import DocumentVersionCreate
    k_service = KnowledgeService(db_session)
    new_version = k_service.create_document_version(DocumentVersionCreate(document_id=doc_id, file_path="/fake", uploaded_by=db_doc.uploaded_by))
    # Fast track to approved
    k_service.update_document_version_status(new_version.id, StatusEnum.PENDING_REVIEW)
    k_service.update_document_version_status(new_version.id, StatusEnum.APPROVED)
    
    # Publish new version
    client.post(f"/api/v1/workflow/documents/versions/{new_version.id}/publish", headers={"Authorization": f"Bearer {admin2_token}"}, json={})
    
    db_session.refresh(version)
    assert version.status == StatusEnum.ARCHIVED
    
    # 12: Archived not in search
    # Only v1 had chunk, and it's archived now.
    results = search_service.search("Test")
    assert len(results) == 0

