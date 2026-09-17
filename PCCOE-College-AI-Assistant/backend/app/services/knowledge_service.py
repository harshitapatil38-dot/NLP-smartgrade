from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
import json

from app.models.document import Document, DocumentVersion
from app.models.faq import FAQ
from app.models.knowledge import KnowledgeSource
from app.models.enums import StatusEnum
from app.schemas.knowledge import (
    DocumentCreate, DocumentVersionCreate, FAQCreate, FAQUpdate, KnowledgeSourceCreate
)
from app.core.exceptions import InvalidStatusTransitionError, ResourceNotFoundError

VALID_TRANSITIONS = {
    StatusEnum.DRAFT: [StatusEnum.PENDING_REVIEW, StatusEnum.ARCHIVED],
    StatusEnum.PENDING_REVIEW: [StatusEnum.DRAFT, StatusEnum.APPROVED, StatusEnum.ARCHIVED],
    StatusEnum.APPROVED: [StatusEnum.PUBLISHED, StatusEnum.DRAFT, StatusEnum.ARCHIVED],
    StatusEnum.PUBLISHED: [StatusEnum.ARCHIVED, StatusEnum.DRAFT],
    StatusEnum.ARCHIVED: [StatusEnum.DRAFT],
}

class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db

    def validate_status_transition(self, current_status: StatusEnum, new_status: StatusEnum):
        if current_status == new_status:
            return
        allowed_next_states = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_next_states:
            raise InvalidStatusTransitionError(
                f"Cannot transition status from {current_status.value} to {new_status.value}"
            )

    # --- Knowledge Source operations ---

    def create_knowledge_source(self, data: KnowledgeSourceCreate) -> KnowledgeSource:
        db_source = KnowledgeSource(**data.model_dump())
        db_source.status = StatusEnum.DRAFT # Default to draft
        self.db.add(db_source)
        self.db.commit()
        self.db.refresh(db_source)
        return db_source

    # --- Document & Version operations ---

    def create_document(self, data: DocumentCreate) -> Document:
        db_doc = Document(**data.model_dump())
        db_doc.status = StatusEnum.DRAFT
        self.db.add(db_doc)
        self.db.commit()
        self.db.refresh(db_doc)
        return db_doc

    def create_document_version(self, data: DocumentVersionCreate) -> DocumentVersion:
        # Verify document exists
        doc = self.db.query(Document).filter(Document.id == data.document_id).first()
        if not doc:
            raise ResourceNotFoundError(f"Document with id {data.document_id} not found")

        # Determine version number deterministically
        max_version = self.db.query(func.max(DocumentVersion.version_number)).filter(
            DocumentVersion.document_id == data.document_id
        ).scalar()
        
        next_version = (max_version or 0) + 1

        db_version = DocumentVersion(
            document_id=data.document_id,
            version_number=next_version,
            file_path=data.file_path,
            uploaded_by=data.uploaded_by,
            status=StatusEnum.DRAFT # Does not publish automatically
        )
        self.db.add(db_version)
        self.db.commit()
        self.db.refresh(db_version)
        return db_version

    def publish_document_version(self, version_id: int) -> DocumentVersion:
        """
        Publishes a version. 
        Requires the version to currently be APPROVED. 
        Will ARCHIVE any other PUBLISHED versions of this document.
        """
        version = self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not version:
            raise ResourceNotFoundError(f"DocumentVersion {version_id} not found")

        self.validate_status_transition(version.status, StatusEnum.PUBLISHED)

        # Archive previously published versions of the same document
        published_versions = self.db.query(DocumentVersion).filter(
            DocumentVersion.document_id == version.document_id,
            DocumentVersion.status == StatusEnum.PUBLISHED,
            DocumentVersion.id != version_id
        ).all()

        for pv in published_versions:
            pv.status = StatusEnum.ARCHIVED
            pv.archived_at = func.now()

        version.status = StatusEnum.PUBLISHED
        version.published_at = func.now()

        # Update parent document status if it wasn't published
        doc = self.db.query(Document).filter(Document.id == version.document_id).first()
        if doc and doc.status != StatusEnum.PUBLISHED:
            doc.status = StatusEnum.PUBLISHED

        self.db.commit()
        self.db.refresh(version)
        return version

    def archive_document_version(self, version_id: int) -> DocumentVersion:
        version = self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not version:
            raise ResourceNotFoundError(f"DocumentVersion {version_id} not found")
        
        self.validate_status_transition(version.status, StatusEnum.ARCHIVED)
        
        version.status = StatusEnum.ARCHIVED
        version.archived_at = func.now()
        self.db.commit()
        self.db.refresh(version)
        return version

    def update_document_version_status(self, version_id: int, new_status: StatusEnum) -> DocumentVersion:
        """General status update for versions. Use publish_document_version for publishing logic."""
        if new_status == StatusEnum.PUBLISHED:
            return self.publish_document_version(version_id)
        if new_status == StatusEnum.ARCHIVED:
            return self.archive_document_version(version_id)
            
        version = self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not version:
            raise ResourceNotFoundError(f"DocumentVersion {version_id} not found")

        self.validate_status_transition(version.status, new_status)
        version.status = new_status
        self.db.commit()
        self.db.refresh(version)
        return version

    # --- FAQ operations ---

    def create_faq(self, data: FAQCreate) -> FAQ:
        db_faq = FAQ(**data.model_dump())
        db_faq.status = StatusEnum.DRAFT
        self.db.add(db_faq)
        self.db.commit()
        self.db.refresh(db_faq)
        return db_faq

    def update_faq(self, faq_id: int, data: FAQUpdate) -> FAQ:
        db_faq = self.db.query(FAQ).filter(FAQ.id == faq_id).first()
        if not db_faq:
            raise ResourceNotFoundError(f"FAQ {faq_id} not found")
        
        update_data = data.model_dump(exclude_unset=True)
        if 'status' in update_data:
            new_status = update_data['status']
            self.validate_status_transition(db_faq.status, new_status)

        for key, value in update_data.items():
            setattr(db_faq, key, value)
            
        self.db.commit()
        self.db.refresh(db_faq)
        return db_faq

    # --- Retrieve operations ---

    def list_published_knowledge(self):
        """
        Retrieves only content that is PUBLISHED or APPROVED depending on the content type.
        For DocumentVersions, we usually fetch PUBLISHED.
        For FAQs, we fetch PUBLISHED.
        """
        published_versions = self.db.query(DocumentVersion).filter(
            DocumentVersion.status == StatusEnum.PUBLISHED
        ).all()

        published_faqs = self.db.query(FAQ).filter(
            FAQ.status == StatusEnum.PUBLISHED
        ).all()

        return {
            "documents": published_versions,
            "faqs": published_faqs
        }
