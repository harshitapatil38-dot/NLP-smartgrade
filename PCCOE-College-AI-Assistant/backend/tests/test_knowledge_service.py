import pytest
from app.services.knowledge_service import KnowledgeService
from app.schemas.knowledge import DocumentCreate, DocumentVersionCreate, FAQCreate, FAQUpdate, KnowledgeSourceCreate
from app.models.enums import StatusEnum
from app.core.exceptions import InvalidStatusTransitionError
from app.models.department import Department

def test_create_knowledge_source(db_session):
    service = KnowledgeService(db_session)
    data = KnowledgeSourceCreate(name="Official Site", source_type="website", source_uri="https://pccoe.edu")
    source = service.create_knowledge_source(data)
    
    assert source.id is not None
    assert source.name == "Official Site"
    assert source.status == StatusEnum.DRAFT

def test_create_document_and_multiple_versions(db_session):
    service = KnowledgeService(db_session)
    
    # Create Document
    doc_data = DocumentCreate(title="Library Rules", category="Library")
    doc = service.create_document(doc_data)
    assert doc.id is not None
    
    # Create Version 1
    v1_data = DocumentVersionCreate(document_id=doc.id, file_path="v1.pdf")
    v1 = service.create_document_version(v1_data)
    assert v1.version_number == 1
    assert v1.status == StatusEnum.DRAFT
    
    # Create Version 2
    v2_data = DocumentVersionCreate(document_id=doc.id, file_path="v2.pdf")
    v2 = service.create_document_version(v2_data)
    assert v2.version_number == 2
    
def test_publish_and_archive_document_version(db_session):
    service = KnowledgeService(db_session)
    doc_data = DocumentCreate(title="Hostel Rules", category="Hostel")
    doc = service.create_document(doc_data)
    
    v1_data = DocumentVersionCreate(document_id=doc.id, file_path="v1.pdf")
    v1 = service.create_document_version(v1_data)
    
    # To publish, we must first approve
    service.update_document_version_status(v1.id, StatusEnum.PENDING_REVIEW)
    service.update_document_version_status(v1.id, StatusEnum.APPROVED)
    
    # Publish version 1
    v1_published = service.publish_document_version(v1.id)
    assert v1_published.status == StatusEnum.PUBLISHED
    
    # Create and publish version 2
    v2_data = DocumentVersionCreate(document_id=doc.id, file_path="v2.pdf")
    v2 = service.create_document_version(v2_data)
    
    service.update_document_version_status(v2.id, StatusEnum.PENDING_REVIEW)
    service.update_document_version_status(v2.id, StatusEnum.APPROVED)
    
    v2_published = service.publish_document_version(v2.id)
    assert v2_published.status == StatusEnum.PUBLISHED
    
    # Check that v1 was archived
    db_session.refresh(v1_published)
    assert v1_published.status == StatusEnum.ARCHIVED

def test_invalid_status_transition(db_session):
    service = KnowledgeService(db_session)
    doc_data = DocumentCreate(title="Exam Schedule")
    doc = service.create_document(doc_data)
    
    v1_data = DocumentVersionCreate(document_id=doc.id, file_path="v1.pdf")
    v1 = service.create_document_version(v1_data)
    
    # DRAFT to PUBLISHED is invalid
    with pytest.raises(InvalidStatusTransitionError):
        service.publish_document_version(v1.id)

def test_create_and_update_faq_with_department(db_session):
    # 1. Create a Department
    dept = Department(name="Computer Engineering", short_code="COMP")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    
    service = KnowledgeService(db_session)
    faq_data = FAQCreate(question="What is CS?", answer="Computer Science", department_id=dept.id)
    faq = service.create_faq(faq_data)
    
    assert faq.department_id == dept.id
    assert faq.status == StatusEnum.DRAFT
    
    # Update FAQ
    service.update_faq(faq.id, FAQUpdate(status=StatusEnum.PENDING_REVIEW))
    db_session.refresh(faq)
    assert faq.status == StatusEnum.PENDING_REVIEW

def test_list_published_knowledge(db_session):
    service = KnowledgeService(db_session)
    
    # 1. Published Document
    doc = service.create_document(DocumentCreate(title="General Info"))
    v1 = service.create_document_version(DocumentVersionCreate(document_id=doc.id, file_path="info.pdf"))
    service.update_document_version_status(v1.id, StatusEnum.PENDING_REVIEW)
    service.update_document_version_status(v1.id, StatusEnum.APPROVED)
    service.publish_document_version(v1.id)
    
    # 2. Published FAQ
    faq = service.create_faq(FAQCreate(question="Q1", answer="A1"))
    service.update_faq(faq.id, FAQUpdate(status=StatusEnum.PENDING_REVIEW))
    service.update_faq(faq.id, FAQUpdate(status=StatusEnum.APPROVED))
    service.update_faq(faq.id, FAQUpdate(status=StatusEnum.PUBLISHED))
    
    # 3. Draft FAQ (Should not be listed)
    draft_faq = service.create_faq(FAQCreate(question="Q2", answer="A2"))
    
    published = service.list_published_knowledge()
    
    assert len(published["documents"]) == 1
    assert published["documents"][0].id == v1.id
    
    assert len(published["faqs"]) == 1
    assert published["faqs"][0].id == faq.id
