import os
import sys
from app.database.database import SessionLocal
from app.services.semantic_search_service import SemanticSearchService
from app.services.rag_service import RAGService
from app.services.llm_service import LLMService, BaseLLMProvider

class MockProvider(BaseLLMProvider):
    def __init__(self):
        super().__init__(model="test", api_key="test")
    def generate(self, system_prompt: str, user_question: str, context: str, **kwargs) -> str:
        if not context or context.strip() == "":
            return "I'm sorry, I don't have enough information in the college knowledge base to answer that question. Please contact the college office for assistance."
        return f"MOCKED ANSWER BASED ON CONTEXT: Context length {len(context)} characters. Question: {user_question}"

LLMService.get_provider = lambda: MockProvider()

db = SessionLocal()
search_service = SemanticSearchService(db)
rag_service = RAGService(db)

questions = [
    "What documents are required for admission?",
    "What facilities are available at PCCOE?",
    "What scholarships are available?",
    "What departments are available?",
    "How can I contact PCCOE?"
]

print("=" * 60)
print("PHASE 6: SEMANTIC SEARCH VALIDATION")
print("=" * 60)

for q in questions:
    print(f"\nQUERY: {q}")
    results = search_service.search(q)
    if results:
        top = results[0]
        print(f"RESULT FOUND: Yes")
        print(f"TOP RESULT TITLE: {top['title']}")
        print(f"SIMILARITY SCORE: {top['similarity_score']}")
        print(f"SOURCE URL: {top['source']}")
    else:
        print("RESULT FOUND: No")

print("\n" + "=" * 60)
print("PHASE 7: RAG VALIDATION")
print("=" * 60)

for q in questions:
    print(f"\nQUERY: {q}")
    result = rag_service.ask(q)
    print(f"ANSWER: {result.answer}")
    if result.sources:
        print(f"CITATIONS: {[s.source for s in result.sources]}")
    else:
        print("CITATIONS: None")

# Unsupported Question
unsupported = "What is the distance between PCCOE and Mars?"
print(f"\nUNSUPPORTED QUERY: {unsupported}")
result = rag_service.ask(unsupported)
print(f"ANSWER: {result.answer}")
if result.sources:
    print(f"CITATIONS: {[s.source for s in result.sources]}")
else:
    print("CITATIONS: None")

db.close()
