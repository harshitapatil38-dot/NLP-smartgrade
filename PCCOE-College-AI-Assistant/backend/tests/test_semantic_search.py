import pytest
from app.services.embedding_service import EmbeddingService
from app.services.semantic_search_service import SemanticSearchService
from app.models.document import Document, DocumentVersion, DocumentChunk
from app.models.enums import StatusEnum

def test_embedding_service_model_loads():
    model = EmbeddingService.get_model()
    assert model is not None
    assert EmbeddingService.get_dimension() == 384

def test_embedding_service_embedding_generation():
    embedding = EmbeddingService.generate_embedding("Test sentence")
    assert len(embedding) == 384
    assert isinstance(embedding[0], float)

def test_embedding_service_semantic_similarity():
    emb1 = EmbeddingService.generate_embedding("The cat sits on the mat")
    emb2 = EmbeddingService.generate_embedding("A feline is resting on the rug")
    emb3 = EmbeddingService.generate_embedding("I love programming in Python")

    # Quick dot product (they are normalized in sentence-transformers usually, so dot product ~ cosine sim)
    sim12 = sum(a * b for a, b in zip(emb1, emb2))
    sim13 = sum(a * b for a, b in zip(emb1, emb3))
    
    assert sim12 > sim13

def test_semantic_search_retrieves_relevant_chunk(db_session):
    # Setup Data
    doc = Document(title="Admission Rules", source="rules.pdf")
    db_session.add(doc)
    db_session.commit()
    
    # Needs to be PUBLISHED to be found
    version = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.PUBLISHED)
    db_session.add(version)
    db_session.commit()

    chunk1_text = "Students must submit their original Leaving Certificate during admission."
    chunk2_text = "The library is open from 9 AM to 5 PM."

    chunk1 = DocumentChunk(
        document_version_id=version.id, 
        chunk_order=1, 
        chunk_text=chunk1_text, 
        embedding=EmbeddingService.generate_embedding(chunk1_text),
        metadata_={"page_number": 1}
    )
    chunk2 = DocumentChunk(
        document_version_id=version.id, 
        chunk_order=2, 
        chunk_text=chunk2_text, 
        embedding=EmbeddingService.generate_embedding(chunk2_text),
        metadata_={"page_number": 2}
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    search_service = SemanticSearchService(db_session)
    results = search_service.search("What documents do I need when taking admission?")

    assert len(results) > 0
    assert results[0]["chunk_id"] == chunk1.id
    assert results[0]["similarity_score"] > 0.3
    assert results[0]["title"] == "Admission Rules"
    assert results[0]["page_number"] == 1

def test_semantic_search_excludes_draft_and_archived(db_session):
    doc = Document(title="Secret Rules")
    db_session.add(doc)
    db_session.commit()
    
    # DRAFT version
    version = DocumentVersion(document_id=doc.id, version_number=1, status=StatusEnum.DRAFT)
    db_session.add(version)
    db_session.commit()

    chunk_text = "This is a secret draft regarding admission."
    chunk = DocumentChunk(
        document_version_id=version.id, 
        chunk_order=1, 
        chunk_text=chunk_text, 
        embedding=EmbeddingService.generate_embedding(chunk_text)
    )
    db_session.add(chunk)
    db_session.commit()

    search_service = SemanticSearchService(db_session)
    results = search_service.search("admission secret")

    # Should not return DRAFT
    assert len(results) == 0
