import pytest
from app.services.ingestion.extractors import HTMLExtractor

def test_html_extractor():
    html_content = """
    <html>
    <head><title>Test Title</title></head>
    <body>
        <nav>Navigation Link</nav>
        <header>Header Text</header>
        <div class="content">
            <h1>Main Topic</h1>
            <p>This is the real PCCOE information.</p>
        </div>
        <script>console.log('test');</script>
        <footer>Copyright 2026</footer>
    </body>
    </html>
    """
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
        temp_file.write(html_content.encode('utf-8'))
        temp_path = temp_file.name

    try:
        pages = HTMLExtractor.extract(temp_path)
        assert len(pages) == 1
        text = pages[0]["text"]
        
        # Extracted text should not include script, nav, header, or footer
        assert "Navigation Link" not in text
        assert "Header Text" not in text
        assert "console.log" not in text
        assert "Copyright" not in text
        
        # Extracted text should include the main content
        assert "Main Topic" in text
        assert "This is the real PCCOE information." in text
        
    finally:
        os.remove(temp_path)

def test_import_workflow(db_session):
    from app.models.document import Document, DocumentVersion, DocumentChunk
    from app.models.enums import StatusEnum, ProcessingStatusEnum
    from app.models.user import User
    from app.models.enums import RoleEnum
    from app.services.ingestion.ingestion_service import DocumentIngestionService
    from app.services.ingestion.storage import LocalStorageService
    from app.services.ingestion.file_validator import FileValidator
    import tempfile
    import os
    
    # 0. Create a mock user
    test_user = User(
        username="testadmin",
        email="testadmin@pccoepune.org",
        hashed_password="fake",
        role=RoleEnum.ADMIN
    )
    db_session.add(test_user)
    db_session.commit()
    
    # 1. Create a mock HTML file in storage
    storage = LocalStorageService()
    html_content = b"<html><body><p>Test admission content for PCCOE</p></body></html>"
    file_path = storage.save_file("test_import.html", html_content)
    
    # 2. Mock the import script behavior (DRAFT Document & Version)
    doc = Document(
        title="Test Admission",
        description="Official content imported",
        category="Admissions",
        source="https://www.pccoepune.com/admission-home.php",
        status=StatusEnum.DRAFT,
        uploaded_by=test_user.id
    )
    db_session.add(doc)
    db_session.commit()
    
    ver = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        status=StatusEnum.DRAFT,
        file_path=file_path
    )
    db_session.add(ver)
    db_session.commit()
    
    # 3. Simulate processing (which happens via Celery/Background task in production when published)
    validator = FileValidator(allowed_extensions=['html'], max_size_mb=10)
    ingestion_service = DocumentIngestionService(db_session, storage_service=storage, file_validator=validator)
    
    # Process it
    updated_ver = ingestion_service.process_document_version(ver.id)
    
    # 4. Assertions
    assert updated_ver.processing_status == ProcessingStatusEnum.COMPLETED
    
    # Check chunks were created
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_version_id == ver.id).all()
    assert len(chunks) > 0
    assert "Test admission content for PCCOE" in chunks[0].chunk_text
    
    # Check that metadata preserved source URL
    assert chunks[0].metadata_["source_url"] == "https://www.pccoepune.com/admission-home.php"

def test_duplicate_prevention_in_import(db_session, monkeypatch):
    import requests
    from scripts.import_pccoe_knowledge import run_import, OFFICIAL_URLS
    from app.models.document import Document, DocumentVersion
    
    # Mock requests.get
    class MockResponse:
        def __init__(self):
            self.content = b"<html><body>Mock Content</body></html>"
        def raise_for_status(self):
            pass
            
    monkeypatch.setattr(requests, "get", lambda url, **kwargs: MockResponse())
    
    # Let's run it once (only on 1 URL for speed, so mock OFFICIAL_URLS)
    mock_urls = [
        {
            "url": "https://www.pccoepune.com/test-dup.php",
            "title": "Dup Test",
            "category": "Test",
            "department_code": None
        }
    ]
    monkeypatch.setattr("scripts.import_pccoe_knowledge.OFFICIAL_URLS", mock_urls)
    
    # Needs to use the test db_session. run_import creates its own SessionLocal.
    # So we'll mock SessionLocal to return a wrapper that doesn't close our db_session
    class MockSession:
        def __init__(self, session):
            self.session = session
        def __getattr__(self, name):
            return getattr(self.session, name)
        def close(self):
            pass # Prevent run_import from closing the test session
            
    monkeypatch.setattr("scripts.import_pccoe_knowledge.SessionLocal", lambda: MockSession(db_session))
    
    # First run
    run_import()
    
    # Check DB
    docs = db_session.query(Document).filter_by(source="https://www.pccoepune.com/test-dup.php").all()
    assert len(docs) == 1
    doc = docs[0]
    
    vers = db_session.query(DocumentVersion).filter_by(document_id=doc.id).order_by(DocumentVersion.version_number.asc()).all()
    assert len(vers) == 1
    assert vers[0].version_number == 1
    
    # Second run
    run_import()
    
    # Check DB again
    docs_again = db_session.query(Document).filter_by(source="https://www.pccoepune.com/test-dup.php").all()
    assert len(docs_again) == 1 # Still 1 document!
    
    vers_again = db_session.query(DocumentVersion).filter_by(document_id=doc.id).order_by(DocumentVersion.version_number.asc()).all()
    assert len(vers_again) == 2 # Now 2 versions!
    assert vers_again[1].version_number == 2
