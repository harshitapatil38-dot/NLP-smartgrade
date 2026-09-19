import os
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.document import DocumentChunk, DocumentVersion, Document
from app.models.enums import StatusEnum
from .embedding_service import EmbeddingService

class SemanticSearchService:
    def __init__(self, db: Session):
        self.db = db
        self.top_k = int(os.environ.get("SEMANTIC_SEARCH_TOP_K", 5))
        self.threshold = float(os.environ.get("SEMANTIC_SEARCH_THRESHOLD", 0.3))

    def search(self, query: str) -> List[Dict[str, Any]]:
        # 1. Generate Query Embedding
        query_embedding = EmbeddingService.generate_embedding(query)

        # 2. Search Database using pgvector cosine distance (<=>)
        # We want similarity, so we can use 1 - cosine_distance or filter by distance < threshold
        # PgVector's <=> operator is cosine distance. 
        # Cosine similarity = 1 - cosine distance. So higher similarity means lower distance.
        max_distance = 1.0 - self.threshold

        # Filter: Only include PUBLISHED document versions
        results = (
            self.db.query(
                DocumentChunk, 
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
            )
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .filter(DocumentVersion.status == StatusEnum.PUBLISHED)
            .filter(DocumentChunk.embedding.cosine_distance(query_embedding) < max_distance)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(self.top_k)
            .all()
        )

        # 3. Format Response
        formatted_results = []
        for chunk, distance in results:
            similarity_score = 1.0 - distance
            version = chunk.version
            doc = version.document
            
            department_name = doc.department.name if doc.department else None
            page_number = chunk.metadata_.get("page_number") if chunk.metadata_ else None
            
            formatted_results.append({
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "document_version_id": version.id,
                "text": chunk.chunk_text,
                "similarity_score": similarity_score,
                "source": doc.source,
                "title": doc.title,
                "department": department_name,
                "page_number": page_number,
                "metadata": chunk.metadata_
            })

        return formatted_results
