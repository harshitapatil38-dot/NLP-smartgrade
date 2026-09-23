from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.deps import get_db, require_roles
from app.models.enums import RoleEnum, StatusEnum
from app.models.user import User
from app.schemas.knowledge import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentDetailResponse
)
from app.services.knowledge_service import KnowledgeService
from app.core.exceptions import ResourceNotFoundError

router = APIRouter(tags=["Documents"])

ADMIN_ROLES = [RoleEnum.ADMIN, RoleEnum.SUPER_ADMIN, RoleEnum.DEPARTMENT_ADMIN]


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[StatusEnum] = None,
    department_id: Optional[int] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES))
):
    """
    List documents with optional filtering.
    """
    service = KnowledgeService(db)
    return service.list_documents(
        skip=skip,
        limit=limit,
        status=status,
        department_id=department_id,
        source=source
    )


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES))
):
    """
    Create a new document draft.
    """
    # Force uploaded_by to current_user if not provided, or ensure audit trail
    if not data.uploaded_by:
        data.uploaded_by = current_user.id
        
    service = KnowledgeService(db)
    return service.create_document(data)

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    department_id: Optional[int] = Form(None),
    source: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES))
):
    """
    Upload a document file and create a new document draft with version 1.
    """
    file_content = await file.read()
    
    from app.services.ingestion.file_validator import FileValidator, FileValidationError
    from app.services.ingestion.storage import LocalStorageService
    import os
    
    max_mb = int(os.environ.get("MAX_UPLOAD_SIZE_MB", 10))
    exts = os.environ.get("ALLOWED_EXTENSIONS", "pdf,docx,txt,html").split(",")
    validator = FileValidator(allowed_extensions=exts, max_size_mb=max_mb)
    
    try:
        validator.validate(file.filename, file_content)
    except FileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    storage = LocalStorageService()
    file_path = storage.save_file(file.filename, file_content)
    
    data = DocumentCreate(
        title=title,
        description=description,
        category=category,
        department_id=department_id,
        source=source,
        uploaded_by=current_user.id
    )
    
    service = KnowledgeService(db)
    doc = service.create_document(data)
    
    from app.schemas.knowledge import DocumentVersionCreate
    version_data = DocumentVersionCreate(
        document_id=doc.id,
        file_path=file_path,
        uploaded_by=current_user.id
    )
    service.create_document_version(version_data)
    
    return doc


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES))
):
    """
    Get detailed information about a document, including versions.
    """
    service = KnowledgeService(db)
    try:
        return service.get_document(document_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES))
):
    """
    Update document metadata. Cannot bypass approval workflows.
    """
    service = KnowledgeService(db)
    try:
        return service.update_document(document_id, data)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ADMIN_ROLES))
):
    """
    Safely delete a document and all its dependencies (versions, chunks, approval records).
    """
    service = KnowledgeService(db)
    try:
        service.delete_document(document_id)
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
