import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.approval import ApprovalRecord
from app.models.enums import RoleEnum, StatusEnum, ProcessingStatusEnum
from app.models.user import User
from app.api.deps import get_current_user

# Mock users for tests
@pytest.fixture
def admin_user(db_session: Session):
    user = User(
        username="admin_api",
        email="admin_api@pccoe.edu",
        role=RoleEnum.ADMIN,
        is_active=True,
        hashed_password="fake"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def faculty_user(db_session: Session):
    user = User(
        username="faculty_api",
        email="faculty_api@pccoe.edu",
        role=RoleEnum.FACULTY,
        is_active=True,
        hashed_password="fake"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def client(db_session: Session):
    from app.database.database import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_unauthenticated_access(client: TestClient):
    response = client.get("/api/v1/documents/")
    assert response.status_code == 401

def test_unauthorized_access(client: TestClient, faculty_user: User):
    app.dependency_overrides[get_current_user] = lambda: faculty_user
    response = client.get("/api/v1/documents/")
    app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 403

def test_create_document(client: TestClient, admin_user: User):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    payload = {
        "title": "New Document",
        "description": "Test Desc",
        "category": "Test"
    }
    response = client.post("/api/v1/documents/", json=payload)
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Document"
    assert data["status"] == StatusEnum.DRAFT.value
    assert data["uploaded_by"] == admin_user.id

def test_list_and_get_document(client: TestClient, db_session: Session, admin_user: User):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    # Create two docs
    doc1 = Document(title="Doc 1", status=StatusEnum.DRAFT)
    doc2 = Document(title="Doc 2", status=StatusEnum.PUBLISHED)
    db_session.add_all([doc1, doc2])
    db_session.commit()
    db_session.refresh(doc1)
    
    # Test Listing
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    
    # Test Filtering by status
    response = client.get("/api/v1/documents/?status=PUBLISHED")
    assert response.status_code == 200
    data = response.json()
    assert all(d["status"] == StatusEnum.PUBLISHED.value for d in data)
    
    # Test Pagination
    response = client.get("/api/v1/documents/?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Test Get Single Document Detail
    response = client.get(f"/api/v1/documents/{doc1.id}")
    assert response.status_code == 200
    assert response.json()["title"] == "Doc 1"
    assert "versions" in response.json()

    app.dependency_overrides.pop(get_current_user, None)

def test_update_document_metadata(client: TestClient, db_session: Session, admin_user: User):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    doc = Document(title="Old Title", status=StatusEnum.PUBLISHED)
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    payload = {"title": "New Title", "description": "New Desc"}
    response = client.put(f"/api/v1/documents/{doc.id}", json=payload)
    
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"
    assert response.json()["description"] == "New Desc"
    assert response.json()["status"] == StatusEnum.PUBLISHED.value # Remains PUBLISHED

def test_delete_document_cascade(client: TestClient, db_session: Session, admin_user: User):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    # Setup extensive graph
    doc = Document(title="To be deleted", status=StatusEnum.DRAFT)
    db_session.add(doc)
    db_session.commit()
    
    ver = DocumentVersion(document_id=doc.id, version_number=1)
    db_session.add(ver)
    db_session.commit()
    
    chunk = DocumentChunk(document_version_id=ver.id, chunk_text="test", chunk_order=1)
    db_session.add(chunk)
    
    approval = ApprovalRecord(
        document_version_id=ver.id, 
        reviewer_id=admin_user.id, 
        action="SUBMIT",
        previous_status=StatusEnum.DRAFT,
        new_status=StatusEnum.PENDING_REVIEW
    )
    db_session.add(approval)
    db_session.commit()
    
    # Verify records exist
    assert db_session.query(Document).filter_by(id=doc.id).first() is not None
    assert db_session.query(DocumentVersion).filter_by(id=ver.id).first() is not None
    assert db_session.query(DocumentChunk).filter_by(id=chunk.id).first() is not None
    assert db_session.query(ApprovalRecord).filter_by(id=approval.id).first() is not None
    
    # Delete API Call
    response = client.delete(f"/api/v1/documents/{doc.id}")
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 204
    
    # Verify cascade deletion
    assert db_session.query(Document).filter_by(id=doc.id).first() is None
    assert db_session.query(DocumentVersion).filter_by(id=ver.id).first() is None
    assert db_session.query(DocumentChunk).filter_by(id=chunk.id).first() is None
    assert db_session.query(ApprovalRecord).filter_by(id=approval.id).first() is None
