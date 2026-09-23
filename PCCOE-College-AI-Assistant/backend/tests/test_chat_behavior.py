import pytest
from app.services.chat_service import ChatService
from app.models.chat import ChatSession, ChatMessage
from app.services.rag_service import RAGResult

class MockProvider:
    def __init__(self, model, api_key):
        self.model = model
        self.api_key = api_key
        self.last_user_question = ""
        
    def generate(self, system_prompt: str, user_question: str, context: str, **kwargs) -> str:
        self.last_user_question = user_question
        # If it's a rewrite request, just return a mocked standalone query
        if "rewrite" in system_prompt.lower():
            if "timings" in user_question.lower() and "library" in user_question.lower():
                return "What are the timings of the library?"
            if "timings" in user_question.lower():
                return "AMBIGUOUS"
            return "What are the clubs?"
        # Standard generate
        return "This is a mock answer."

def test_greeting_behavior(db_session):
    chat_service = ChatService(db_session)
    
    token, result = chat_service.process_chat("Hello")
    assert result.retrieved_chunks == 0
    assert "admissions, departments, courses" in result.answer

    token, result2 = chat_service.process_chat("help", session_token=token)
    assert result2.retrieved_chunks == 0
    assert "admissions, departments, courses" in result2.answer

def test_ambiguous_question_without_history(db_session):
    chat_service = ChatService(db_session)
    token, result = chat_service.process_chat("what are the timings?")
    
    assert result.retrieved_chunks == 0
    assert "Could you specify which area you mean" in result.answer

def test_follow_up_contextualization(db_session, monkeypatch):
    import app.services.llm_service
    # Patch the provider factory to return our mock provider
    monkeypatch.setattr(app.services.llm_service.LLMService, "get_provider", lambda: MockProvider("mock", "key"))
    
    # Also patch rag_service so it doesn't actually search DB
    class MockRAGService:
        def __init__(self, db):
            pass
        def ask(self, query, conversation_history=None, original_question=None):
            # Verify the query has been rewritten
            assert query == "What are the timings of the library?"
            return RAGResult(answer="Library timings are 9 to 5.", sources=[], query=query, retrieved_chunks=1)
            
    monkeypatch.setattr("app.services.chat_service.RAGService", MockRAGService)

    chat_service = ChatService(db_session)
    
    # Add fake history
    session = chat_service.get_or_create_session()
    msg1 = ChatMessage(session_id=session.id, role="user", content="Tell me about the library.")
    msg2 = ChatMessage(session_id=session.id, role="assistant", content="We have a great library.")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    # Process follow up
    token, result = chat_service.process_chat("what are its timings?", session_token=session.session_token)
    assert result.answer == "Library timings are 9 to 5."

def test_ambiguous_question_with_history(db_session, monkeypatch):
    import app.services.llm_service
    monkeypatch.setattr(app.services.llm_service.LLMService, "get_provider", lambda: MockProvider("mock", "key"))
    
    chat_service = ChatService(db_session)
    
    session = chat_service.get_or_create_session()
    msg1 = ChatMessage(session_id=session.id, role="user", content="Tell me something random.")
    msg2 = ChatMessage(session_id=session.id, role="assistant", content="Okay.")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    # Process follow up that will return AMBIGUOUS from mock LLM
    token, result = chat_service.process_chat("what are the timings?", session_token=session.session_token)
    assert "Could you specify which area you mean" in result.answer
