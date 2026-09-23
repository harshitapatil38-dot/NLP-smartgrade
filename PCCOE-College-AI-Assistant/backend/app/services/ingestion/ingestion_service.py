import os
from sqlalchemy.orm import Session
from app.models.document import DocumentVersion, DocumentChunk
from app.models.enums import ProcessingStatusEnum
from .file_validator import FileValidator, FileValidationError
from .storage import StorageService
from .extractors import ExtractorService, ExtractionError
from .cleaner import TextCleaner
from .chunker import TextChunker
from app.services.chunk_embedder_service import ChunkEmbedderService

class DocumentIngestionService:
    def __init__(
        self,
        db: Session,
        storage_service: StorageService,
        file_validator: FileValidator = None,
        chunker: TextChunker = None
    ):
        self.db = db
        self.storage_service = storage_service
        
        # Load configurable limits from env or use defaults
        max_mb = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 10))
        exts = os.environ.get("ALLOWED_EXTENSIONS", "pdf,docx,txt").split(",")
        self.file_validator = file_validator or FileValidator(allowed_extensions=exts, max_size_mb=max_mb)
        
        chunk_size = int(os.environ.get("CHUNK_SIZE", 1000))
        overlap = int(os.environ.get("CHUNK_OVERLAP", 200))
        self.chunker = chunker or TextChunker(chunk_size=chunk_size, overlap=overlap)

    def process_document_version(self, version_id: int, filename: str = None, file_content: bytes = None):
        """
        Orchestrates the ingestion pipeline for a specific document version.
        If filename and file_content are provided, it saves the file.
        Otherwise, it assumes version.file_path is already populated.
        Returns the updated DocumentVersion.
        """
        version = self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not version:
            raise ValueError(f"DocumentVersion {version_id} not found")

        # 1. Update Processing Status
        version.processing_status = ProcessingStatusEnum.PROCESSING
        self.db.commit()

        try:
            if filename and file_content:
                # 2. File Validation
                self.file_validator.validate(filename, file_content)

                # 3. Storage
                file_path = self.storage_service.save_file(filename, file_content)
                version.file_path = file_path
                self.db.commit()
            else:
                file_path = version.file_path
                if not file_path:
                    raise ValueError(f"No file_path set for version {version_id}")
                if not filename:
                    filename = os.path.basename(file_path)

            # 4. Text Extraction
            ext = filename.split('.')[-1].lower() if '.' in filename else ''
            pages = ExtractorService.extract(file_path, ext)

            # 5. Text Cleaning
            for page in pages:
                page["text"] = TextCleaner.clean(page["text"])

            # 6. Chunking
            chunks_data = self.chunker.chunk_text(pages)

            # 7. Persist Chunks (Idempotent: delete existing chunks for this version)
            self.db.query(DocumentChunk).filter(DocumentChunk.document_version_id == version_id).delete()
            
            for chunk_data in chunks_data:
                metadata = chunk_data["metadata_"] or {}
                metadata["source_url"] = version.document.source if version.document.source else None
                
                chunk = DocumentChunk(
                    document_version_id=version_id,
                    chunk_text=chunk_data["chunk_text"],
                    chunk_order=chunk_data["chunk_order"],
                    metadata_=metadata
                )
                self.db.add(chunk)
            self.db.commit()

            # 7b. Generate Embeddings for Chunks
            embedder = ChunkEmbedderService(self.db)
            embedder.embed_chunks_for_version(version_id)

            # 8. Mark Completed
            version.processing_status = ProcessingStatusEnum.COMPLETED
            self.db.commit()

        except Exception as e:
            version.processing_status = ProcessingStatusEnum.FAILED
            self.db.commit()
            raise Exception(f"Ingestion failed: {str(e)}") from e

        self.db.refresh(version)
        return version
