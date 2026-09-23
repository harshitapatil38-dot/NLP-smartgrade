import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.enums import StatusEnum, ProcessingStatusEnum, RoleEnum
from app.models.user import User
from app.main import app
from app.database.database import get_db
from app.core.security import get_password_hash

@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# This will test the /publish endpoint behavior regarding processing
# and the /retry-processing endpoint.

@pytest.fixture
def test_user(db_session: Session):
    user = User(
        username="admin_processing", 
        email="admin_processing@pccoe.edu", 
        role=RoleEnum.ADMIN, 
        is_active=True,
        hashed_password="fake"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def mock_background_tasks():
    with patch("fastapi.BackgroundTasks.add_task") as mock:
        yield mock

def test_publish_triggers_processing(client: TestClient, db_session: Session, test_user: User, mock_background_tasks):
    # Setup document in APPROVED state
    doc = Document(title="Process Test", status=StatusEnum.APPROVED)
    db_session.add(doc)
    db_session.commit()
    
    version = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.APPROVED)
    db_session.add(version)
    db_session.commit()
    
    # Authenticate as ADMIN
    from app.api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    # Call Publish
    response = client.post(
        f"/api/v1/workflow/documents/versions/{version.id}/publish",
        json={"comment": "publish and process"}
    )
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 200
    db_session.refresh(version)
    assert version.status == StatusEnum.PUBLISHED
    
    # Check if background task was called
    mock_background_tasks.assert_called_once()
    args, kwargs = mock_background_tasks.call_args
    assert args[1] == version.id


def test_retry_processing_success(client: TestClient, db_session: Session, test_user: User, mock_background_tasks):
    doc = Document(title="Retry Test", status=StatusEnum.PUBLISHED)
    db_session.add(doc)
    db_session.commit()
    
    version = DocumentVersion(
        document_id=doc.id, 
        version_number=1, 
        status=StatusEnum.PUBLISHED,
        processing_status=ProcessingStatusEnum.FAILED
    )
    db_session.add(version)
    db_session.commit()
    
    # Authenticate
    from app.api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    response = client.post(
        f"/api/v1/workflow/documents/versions/{version.id}/retry-processing"
    )
    app.dependency_overrides.pop(get_current_user, None)
    
    assert response.status_code == 200
    db_session.refresh(version)
    assert version.processing_status == ProcessingStatusEnum.PENDING
    
    mock_background_tasks.assert_called_once()


def test_retry_processing_invalid_states(client: TestClient, db_session: Session, test_user: User):
    # Authenticate
    from app.api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: test_user
    
    # 1. Not PUBLISHED
    doc1 = Document(title="Not Pub", status=StatusEnum.DRAFT)
    db_session.add(doc1)
    db_session.commit()
    v1 = DocumentVersion(document_id=doc1.id, version_number=1, status=StatusEnum.DRAFT, processing_status=ProcessingStatusEnum.FAILED)
    db_session.add(v1)
    db_session.commit()
    
    r1 = client.post(f"/api/v1/workflow/documents/versions/{v1.id}/retry-processing")
    assert r1.status_code == 409
    assert "PUBLISHED" in r1.json()["detail"]
    
    # 2. Not FAILED
    doc2 = Document(title="Not Failed", status=StatusEnum.PUBLISHED)
    db_session.add(doc2)
    db_session.commit()
    v2 = DocumentVersion(document_id=doc2.id, version_number=1, status=StatusEnum.PUBLISHED, processing_status=ProcessingStatusEnum.COMPLETED)
    db_session.add(v2)
    db_session.commit()
    
    r2 = client.post(f"/api/v1/workflow/documents/versions/{v2.id}/retry-processing")
    assert r2.status_code == 409
    assert "FAILED" in r2.json()["detail"]
    
    app.dependency_overrides.pop(get_current_user, None)


def test_process_published_document_task(db_session: Session, tmpdir):
    from app.tasks.processing_tasks import process_published_document
    from app.services.ingestion.storage import LocalStorageService
    import os
    
    # We will test the actual background task function here, simulating what it does.
    # To do this safely without mocking DB (since it creates SessionLocal), we can just call process_document_version directly to test status changes.
    from app.services.ingestion.ingestion_service import DocumentIngestionService
    
    test_storage_dir = str(tmpdir.mkdir("storage"))
    storage = LocalStorageService(base_dir=test_storage_dir)
    service = DocumentIngestionService(db_session, storage_service=storage)

    doc = Document(title="Process Task Test", status=StatusEnum.PUBLISHED)
    db_session.add(doc)
    db_session.commit()
    
    # Create dummy file to simulate existing upload
    file_path = os.path.join(test_storage_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Some dummy content to chunk")
        
    version = DocumentVersion(
        document_id=doc.id, 
        version_number=1, 
        status=StatusEnum.PUBLISHED,
        processing_status=ProcessingStatusEnum.PENDING,
        file_path=file_path
    )
    db_session.add(version)
    db_session.commit()
    
    # Execute processing (normally done via task, we do it directly to use db_session)
    service.process_document_version(version.id)
    
    db_session.refresh(version)
    assert version.processing_status == ProcessingStatusEnum.COMPLETED
    
    # Check if chunks exist
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_version_id == version.id).all()
    assert len(chunks) > 0
    # Check if embedding was populated (it might be mocked, or run normally if EmbeddingService works locally)
    for c in chunks:
        assert c.embedding is not None

