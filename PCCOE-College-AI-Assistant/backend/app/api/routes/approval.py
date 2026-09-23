from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.user import User
from app.models.enums import RoleEnum
from app.services.approval_service import ApprovalService
from app.tasks.processing_tasks import process_published_document

router = APIRouter(tags=["Approval"])

class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = None

@router.post("/documents/versions/{version_id}/submit")
def submit_for_review(
    version_id: int, 
    request: ApprovalActionRequest,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Submit a DRAFT document version for review."""
    service = ApprovalService(db)
    version = service.submit_for_review(version_id, current_user, request.comment)
    return {"message": "Submitted for review successfully", "status": version.status.value}

@router.post("/documents/versions/{version_id}/approve", dependencies=[Depends(require_roles([RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]))])
def approve_content(
    version_id: int, 
    request: ApprovalActionRequest,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Approve a PENDING_REVIEW document version."""
    service = ApprovalService(db)
    version = service.approve(version_id, current_user, request.comment)
    return {"message": "Approved successfully", "status": version.status.value}

@router.post("/documents/versions/{version_id}/reject", dependencies=[Depends(require_roles([RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]))])
def reject_content(
    version_id: int, 
    request: ApprovalActionRequest,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Reject a PENDING_REVIEW document version, returning it to DRAFT."""
    service = ApprovalService(db)
    version = service.reject(version_id, current_user, request.comment)
    return {"message": "Rejected successfully", "status": version.status.value}

@router.post("/documents/versions/{version_id}/publish", dependencies=[Depends(require_roles([RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]))])
def publish_content(
    version_id: int, 
    request: ApprovalActionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Publish an APPROVED document version and trigger background processing."""
    service = ApprovalService(db)
    version = service.publish(version_id, current_user, request.comment)
    
    background_tasks.add_task(process_published_document, version.id)
    return {"message": "Published successfully", "status": version.status.value}

@router.post("/documents/versions/{version_id}/archive", dependencies=[Depends(require_roles([RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]))])
def archive_content(
    version_id: int, 
    request: ApprovalActionRequest,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Archive a PUBLISHED document version."""
    service = ApprovalService(db)
    version = service.archive(version_id, current_user, request.comment)
    return {"message": "Archived successfully", "status": version.status.value}

@router.post("/documents/versions/{version_id}/retry-processing", dependencies=[Depends(require_roles([RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]))])
def retry_processing(
    version_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Retry processing for a document version that failed."""
    from app.models.document import DocumentVersion
    from app.models.enums import StatusEnum, ProcessingStatusEnum
    from fastapi import HTTPException
    
    version = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found.")
        
    if version.status != StatusEnum.PUBLISHED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Can only retry processing for PUBLISHED versions.")
        
    if version.processing_status != ProcessingStatusEnum.FAILED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Can only retry if processing status is FAILED.")
        
    version.processing_status = ProcessingStatusEnum.PENDING
    db.commit()
    
    background_tasks.add_task(process_published_document, version.id)
    return {"message": "Retry triggered successfully", "processing_status": version.processing_status.value}
