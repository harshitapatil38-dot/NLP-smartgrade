from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database.database import Base
from .enums import StatusEnum, ProcessingStatusEnum

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text)
    category = Column(String, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"))
    source = Column(String)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(StatusEnum), default=StatusEnum.DRAFT, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    department = relationship("Department", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    status = Column(Enum(StatusEnum), default=StatusEnum.DRAFT, nullable=False)
    processing_status = Column(Enum(ProcessingStatusEnum), default=ProcessingStatusEnum.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))

    document = relationship("Document", back_populates="versions")
    chunks = relationship("DocumentChunk", back_populates="version")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_version_id = Column(Integer, ForeignKey("document_versions.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_order = Column(Integer, nullable=False)
    metadata_ = Column("metadata", JSON)  # using metadata_ because metadata is reserved in SQLAlchemy
    embedding = Column(Vector(384))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


    version = relationship("DocumentVersion", back_populates="chunks")
