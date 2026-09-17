from sqlalchemy import Column, Integer, String, Enum, DateTime
from sqlalchemy.sql import func
from app.database.database import Base
from .enums import StatusEnum

class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # e.g. website, file, api
    source_uri = Column(String, nullable=False)
    last_synced_at = Column(DateTime(timezone=True))
    status = Column(Enum(StatusEnum), default=StatusEnum.APPROVED, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
