import logging
from app.database.database import SessionLocal
from app.services.ingestion.ingestion_service import DocumentIngestionService
from app.services.ingestion.storage import LocalStorageService

logger = logging.getLogger(__name__)

def process_published_document(version_id: int):
    """
    Background task to process a published document version.
    It orchestrates extraction, chunking, and embedding.
    """
    db = SessionLocal()
    try:
        storage = LocalStorageService()
        service = DocumentIngestionService(db, storage_service=storage)
        service.process_document_version(version_id)
        logger.info(f"Successfully processed document version {version_id}")
    except Exception as e:
        logger.error(f"Failed to process document version {version_id}: {str(e)}")
    finally:
        db.close()
