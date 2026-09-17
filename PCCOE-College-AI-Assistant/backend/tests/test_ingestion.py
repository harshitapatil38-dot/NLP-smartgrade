import pytest
import os
from io import BytesIO
from app.services.ingestion.file_validator import FileValidator, FileValidationError
from app.services.ingestion.storage import LocalStorageService
from app.services.ingestion.cleaner import TextCleaner
from app.services.ingestion.chunker import TextChunker
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.enums import StatusEnum, ProcessingStatusEnum

def test_file_validator():
    validator = FileValidator(allowed_extensions=['txt'], max_size_mb=1)
    
    # 1. Reject unsupported
    with pytest.raises(FileValidationError, match="Unsupported file extension"):
        validator.validate("test.pdf", b"dummy")
        
    # 2. Reject empty
    with pytest.raises(FileValidationError, match="File is empty"):
        validator.validate("test.txt", b"")
        
    # 3. Reject oversized
    large_content = b"a" * (1024 * 1024 + 10)
    with pytest.raises(FileValidationError, match="File size exceeds"):
        validator.validate("large.txt", large_content)
        
    # 4. Valid
    assert validator.validate("test.txt", b"valid content") is True

def test_text_cleaner():
    raw = "Hello   world.\n\n\nThis is a \x00test."
    cleaned = TextCleaner.clean(raw)
    assert cleaned == "Hello world.\n\nThis is a test."

def test_chunker():
    chunker = TextChunker(chunk_size=10, overlap=2)
    pages = [{"text": "0123456789ABCDEF", "page_number": 1}]
    chunks = chunker.chunk_text(pages)
    
    assert len(chunks) > 1
    assert chunks[0]["chunk_text"] == "0123456789"
    assert chunks[0]["metadata_"] == {"page_number": 1}
    # Notice that due to overlap (2) and start shifting, 
    # the second chunk will start at index 10 - 2 = 8.
    assert chunks[1]["chunk_text"].startswith("89")

def test_end_to_end_ingestion(db_session, tmpdir):
    # Setup test file
    test_storage_dir = str(tmpdir.mkdir("storage"))
    storage = LocalStorageService(base_dir=test_storage_dir)
    service = DocumentIngestionService(db_session, storage_service=storage)

    # 1. Create a Document & Version in DB (simulating Step 3 output)
    doc = Document(title="Ingestion Test", status=StatusEnum.DRAFT)
    db_session.add(doc)
    db_session.commit()
    
    version = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.DRAFT)
    db_session.add(version)
    db_session.commit()

    # 2. Process TXT file
    file_content = b"This is a test document.\n\nIt has multiple paragraphs.\nAnd some text to chunk."
    filename = "test_doc.txt"

    processed_version = service.process_document_version(version.id, filename, file_content)

    # 3. Verify Statuses (Processing = COMPLETED, Publication = DRAFT)
    assert processed_version.processing_status == ProcessingStatusEnum.COMPLETED
    assert processed_version.status == StatusEnum.DRAFT
    
    # 4. Verify Storage
    assert processed_version.file_path is not None
    assert os.path.exists(processed_version.file_path)

    # 5. Verify Chunks were created in DB
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_version_id == version.id).all()
    assert len(chunks) > 0
    assert chunks[0].chunk_text.startswith("This is a test document.")

    # 6. Verify Idempotency (Reprocessing doesn't duplicate chunks)
    original_chunk_count = len(chunks)
    service.process_document_version(version.id, filename, file_content)
    
    chunks_after = db_session.query(DocumentChunk).filter(DocumentChunk.document_version_id == version.id).all()
    assert len(chunks_after) == original_chunk_count

def test_ingestion_failure(db_session, tmpdir):
    test_storage_dir = str(tmpdir.mkdir("storage"))
    storage = LocalStorageService(base_dir=test_storage_dir)
    service = DocumentIngestionService(db_session, storage_service=storage)
    
    doc = Document(title="Fail Test")
    db_session.add(doc)
    db_session.commit()
    version = DocumentVersion(document_id=doc.id, version_number=1)
    db_session.add(version)
    db_session.commit()

    # Process with bad extension, which throws validation error
    with pytest.raises(Exception, match="Ingestion failed"):
        service.process_document_version(version.id, "bad.exe", b"bad content")
        
    db_session.refresh(version)
    assert version.processing_status == ProcessingStatusEnum.FAILED
