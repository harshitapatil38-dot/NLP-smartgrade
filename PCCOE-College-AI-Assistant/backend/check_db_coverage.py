import os
import sys
from app.database.database import SessionLocal
from app.models.document import Document, DocumentVersion, DocumentChunk

db = SessionLocal()

print("PCCOE KNOWLEDGE COVERAGE REPORT")
print("-" * 50)
docs = db.query(Document).all()
for doc in docs:
    print(f"Title: {doc.title}")
    print(f"  Source: {doc.source}")
    print(f"  Category: {doc.category}")
    print(f"  Status: {doc.status.name}")
    
    published_ver = None
    versions = doc.versions
    print(f"  Versions: {len(versions)}")
    for ver in versions:
        chunks_count = db.query(DocumentChunk).filter(DocumentChunk.document_version_id == ver.id).count()
        embedded_count = db.query(DocumentChunk).filter(DocumentChunk.document_version_id == ver.id, DocumentChunk.embedding != None).count()
        print(f"    v{ver.version_number}: {ver.status.name} | Processing: {ver.processing_status.name} | Chunks: {chunks_count} | Embeddings: {embedded_count}")
        if ver.status.name == "PUBLISHED":
            published_ver = ver
            
    if published_ver:
        print(f"  -> PUBLISHED (Chatbot Retrievable)")
    else:
        print(f"  -> NOT PUBLISHED (Not Accessible)")
    print("")

db.close()
