import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.models.enums import RoleEnum, StatusEnum
from app.models.document import Document, DocumentVersion
from app.models.user import User
from app.models.approval import ApprovalRecord

client = TestClient(app)

def _create_mock_user(id_val, role):
    username = f"{role.value.lower()}_{id_val}"
    return User(id=id_val, email=f"{role.value.lower()}_{id_val}@test.com", username=username, role=role, is_active=True, hashed_password="fake")

@pytest.fixture
def override_db(db_session):
    from app.database.database import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    yield
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    from app.api.deps import get_current_user
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def mock_faculty():
    return _create_mock_user(10, RoleEnum.FACULTY)

@pytest.fixture
def mock_admin():
    return _create_mock_user(20, RoleEnum.ADMIN)

@pytest.fixture
def setup_document(db_session, mock_faculty):
    # Ensure users exist in DB for foreign keys
    db_session.add(mock_faculty)
    admin = _create_mock_user(20, RoleEnum.ADMIN)
    db_session.add(admin)
    db_session.commit()

    doc = Document(title="Test Doc", category="Test", status=StatusEnum.DRAFT)
    db_session.add(doc)
    db_session.commit()
    
    version = DocumentVersion(document_id=doc.id, version_number=1, file_path="test.pdf", uploaded_by=mock_faculty.id, status=StatusEnum.DRAFT)
    db_session.add(version)
    db_session.commit()
    return version

def test_draft_to_pending_review_succeeds(setup_document, mock_faculty, db_session, override_db):
    app.dependency_overrides[get_current_user] = lambda: mock_faculty
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/submit", json={"comment": "Ready for review"})
    assert response.status_code == 200
    assert response.json()["status"] == StatusEnum.PENDING_REVIEW.value
    
    # Audit check
    records = db_session.query(ApprovalRecord).filter_by(document_version_id=setup_document.id).all()
    assert len(records) == 1
    assert records[0].action == "SUBMIT"
    assert records[0].reviewer_id == mock_faculty.id
    assert records[0].comment == "Ready for review"

def test_draft_to_approved_rejected(setup_document, mock_admin, override_db):
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/approve", json={})
    assert response.status_code == 409 # Conflict, not pending review

def test_pending_review_to_approved_succeeds(setup_document, mock_admin, db_session, override_db):
    # First submit
    setup_document.status = StatusEnum.PENDING_REVIEW
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/approve", json={})
    assert response.status_code == 200
    assert response.json()["status"] == StatusEnum.APPROVED.value

def test_pending_review_to_draft_succeeds(setup_document, mock_admin, db_session, override_db):
    setup_document.status = StatusEnum.PENDING_REVIEW
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/reject", json={"comment": "Needs work"})
    assert response.status_code == 200
    assert response.json()["status"] == StatusEnum.DRAFT.value
    
    records = db_session.query(ApprovalRecord).filter_by(action="REJECT").all()
    assert len(records) == 1
    assert records[0].previous_status == StatusEnum.PENDING_REVIEW

def test_approved_to_published_succeeds(setup_document, mock_admin, db_session, override_db):
    setup_document.status = StatusEnum.APPROVED
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/publish", json={})
    assert response.status_code == 200
    assert response.json()["status"] == StatusEnum.PUBLISHED.value
    
    # Parent document should also be updated by knowledge_service
    db_session.refresh(setup_document.document)
    assert setup_document.document.status == StatusEnum.PUBLISHED

def test_published_to_archived_succeeds(setup_document, mock_admin, db_session, override_db):
    setup_document.status = StatusEnum.PUBLISHED
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/archive", json={})
    assert response.status_code == 200
    assert response.json()["status"] == StatusEnum.ARCHIVED.value

def test_unauthorized_role_rejected(setup_document, mock_faculty, db_session, override_db):
    setup_document.status = StatusEnum.PENDING_REVIEW
    db_session.commit()
    
    # Faculty tries to approve (unauthorized)
    app.dependency_overrides[get_current_user] = lambda: mock_faculty
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/approve", json={})
    assert response.status_code == 403

def test_author_cannot_approve_own_submission(setup_document, db_session, override_db):
    setup_document.status = StatusEnum.PENDING_REVIEW
    db_session.commit()
    
    # Create an admin who is the author
    author_admin = _create_mock_user(30, RoleEnum.ADMIN)
    db_session.add(author_admin)
    db_session.commit()
    setup_document.uploaded_by = author_admin.id
    db_session.commit()
    
    app.dependency_overrides[get_current_user] = lambda: author_admin
    response = client.post(f"/api/v1/workflow/documents/versions/{setup_document.id}/approve", json={})
    assert response.status_code == 403
    assert "cannot approve your own submission" in response.text
