from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.document import DocumentVersion
from app.models.approval import ApprovalRecord
from app.models.enums import StatusEnum, RoleEnum
from app.models.user import User
from app.services.knowledge_service import KnowledgeService
from app.core.exceptions import InvalidStatusTransitionError


class ApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.knowledge_service = KnowledgeService(db)

    def submit_for_review(self, version_id: int, current_user: User, comment: Optional[str] = None) -> DocumentVersion:
        version = self._get_version(version_id)
        if version.status != StatusEnum.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only DRAFT content can be submitted for review.")
        
        return self._transition(version, current_user, StatusEnum.PENDING_REVIEW, "SUBMIT", comment)

    def approve(self, version_id: int, current_user: User, comment: Optional[str] = None) -> DocumentVersion:
        self._require_admin(current_user)
        version = self._get_version(version_id)
        
        if version.status != StatusEnum.PENDING_REVIEW:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only PENDING_REVIEW content can be approved.")
        
        if version.uploaded_by == current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot approve your own submission.")
            
        return self._transition(version, current_user, StatusEnum.APPROVED, "APPROVE", comment)

    def reject(self, version_id: int, current_user: User, comment: Optional[str] = None) -> DocumentVersion:
        self._require_admin(current_user)
        version = self._get_version(version_id)
        
        if version.status != StatusEnum.PENDING_REVIEW:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only PENDING_REVIEW content can be rejected.")
            
        return self._transition(version, current_user, StatusEnum.DRAFT, "REJECT", comment)

    def publish(self, version_id: int, current_user: User, comment: Optional[str] = None) -> DocumentVersion:
        self._require_admin(current_user)
        version = self._get_version(version_id)
        
        if version.status != StatusEnum.APPROVED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only APPROVED content can be published.")
            
        return self._transition(version, current_user, StatusEnum.PUBLISHED, "PUBLISH", comment)

    def archive(self, version_id: int, current_user: User, comment: Optional[str] = None) -> DocumentVersion:
        self._require_admin(current_user)
        version = self._get_version(version_id)
        
        if version.status != StatusEnum.PUBLISHED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only PUBLISHED content can be archived.")
            
        return self._transition(version, current_user, StatusEnum.ARCHIVED, "ARCHIVE", comment)

    def _transition(self, version: DocumentVersion, user: User, new_status: StatusEnum, action: str, comment: Optional[str]) -> DocumentVersion:
        previous_status = version.status
        
        try:
            try:
                # Delegate state transition to KnowledgeService to handle complex logic (e.g., archiving old versions on publish)
                version = self.knowledge_service.update_document_version_status(version.id, new_status)
            except InvalidStatusTransitionError as e:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
            
            record = ApprovalRecord(
                document_version_id=version.id,
                reviewer_id=user.id,
                action=action,
                previous_status=previous_status,
                new_status=new_status,
                comment=comment
            )
            
            self.db.add(record)
            self.db.commit()
            self.db.refresh(version)
            return version
        except Exception:
            self.db.rollback()
            raise

    def _get_version(self, version_id: int) -> DocumentVersion:
        version = self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found.")
        return version

    def _require_admin(self, user: User):
        if user.role not in [RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permissions required.")
