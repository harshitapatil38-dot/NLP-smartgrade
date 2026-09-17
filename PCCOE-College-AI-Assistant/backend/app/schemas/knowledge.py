from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.enums import StatusEnum, ProcessingStatusEnum

# --- Document Schemas ---

class DocumentBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    department_id: Optional[int] = None
    source: Optional[str] = None

class DocumentCreate(DocumentBase):
    uploaded_by: Optional[int] = None

class DocumentResponse(DocumentBase):
    id: int
    status: StatusEnum
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class DocumentVersionBase(BaseModel):
    file_path: Optional[str] = None

class DocumentVersionCreate(DocumentVersionBase):
    document_id: int
    uploaded_by: Optional[int] = None

class DocumentVersionResponse(DocumentVersionBase):
    id: int
    document_id: int
    version_number: int
    status: StatusEnum
    processing_status: ProcessingStatusEnum
    uploaded_by: Optional[int] = None
    created_at: datetime
    published_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)



# --- FAQ Schemas ---

class FAQBase(BaseModel):
    question: str
    answer: str
    category: Optional[str] = None
    department_id: Optional[int] = None
    source: Optional[str] = None

class FAQCreate(FAQBase):
    created_by: Optional[int] = None

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    department_id: Optional[int] = None
    source: Optional[str] = None
    status: Optional[StatusEnum] = None
    updated_by: Optional[int] = None

class FAQResponse(FAQBase):
    id: int
    status: StatusEnum
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# --- KnowledgeSource Schemas ---

class KnowledgeSourceBase(BaseModel):
    name: str
    source_type: str
    source_uri: str

class KnowledgeSourceCreate(KnowledgeSourceBase):
    pass

class KnowledgeSourceResponse(KnowledgeSourceBase):
    id: int
    status: StatusEnum
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
