from sqlalchemy.orm import Session
from app.models.document import DocumentChunk
from app.services.embedding_service import EmbeddingService

class ChunkEmbedderService:
    def __init__(self, db: Session):
        self.db = db

    def embed_chunks_for_version(self, document_version_id: int):
        """
        Finds all chunks for a given document version that do not have an embedding,
        generates the embedding, and saves it.
        """
        chunks = (
            self.db.query(DocumentChunk)
            .filter(DocumentChunk.document_version_id == document_version_id)
            .filter(DocumentChunk.embedding == None)
            .all()
        )

        if not chunks:
            return 0

        # Batch process embeddings
        texts = [chunk.chunk_text for chunk in chunks]
        embeddings = EmbeddingService.generate_embeddings_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        self.db.commit()
        return len(chunks)
