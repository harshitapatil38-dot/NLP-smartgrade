import uuid
import os
import json
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.chat import ChatSession, ChatMessage
from app.services.rag_service import RAGService, RAGResult

class ChatService:
    """Service to manage conversational state and message persistence."""

    def __init__(self, db: Session):
        self.db = db
        self.history_limit = int(os.environ.get("CHAT_HISTORY_LIMIT", 10))
        self.rag_service = RAGService(db)

    def get_or_create_session(self, session_token: Optional[str] = None) -> ChatSession:
        """Retrieve an existing session or create a new one."""
        if session_token:
            session = self.db.query(ChatSession).filter(ChatSession.session_token == session_token).first()
            if session:
                return session

        new_token = str(uuid.uuid4())
        session = ChatSession(session_token=new_token)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_chat_history(self, session_id: int) -> str:
        """
        Retrieve recent messages for the given session and format them
        into a conversation history string.
        """
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(self.history_limit)
            .all()
        )

        if not messages:
            return ""

        # Reverse to chronological order
        messages.reverse()

        history_lines = []
        for msg in messages:
            role = "User" if msg.role == "user" else "Assistant"
            history_lines.append(f"{role}: {msg.content}")

        return "\n\n".join(history_lines)

    def process_chat(self, question: str, session_token: Optional[str] = None) -> Tuple[str, RAGResult]:
        """
        Process a user question within a conversation session.
        1. Gets/creates session.
        2. Retrieves history.
        3. Calls RAG service with history.
        4. Saves user and assistant messages to the database.
        """
        # 1. Get or create session
        session = self.get_or_create_session(session_token)

        # 2. Get formatted history
        history_str = self.get_chat_history(session.id)

        # 3. Save user message first so we have a record even if RAG fails
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=question
        )
        self.db.add(user_msg)
        self.db.commit()

        # 4. Perform RAG query
        rag_result = self.rag_service.ask(question, conversation_history=history_str)

        # 5. Save assistant message
        # Convert sources to JSON-serializable dicts
        sources_json = []
        for s in rag_result.sources:
            sources_json.append({
                "document_id": s.document_id,
                "document_version_id": s.document_version_id,
                "chunk_id": s.chunk_id,
                "title": s.title,
                "source": s.source,
                "page_number": s.page_number,
                "similarity_score": s.similarity_score,
                "department": s.department
            })

        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=rag_result.answer,
            retrieved_sources=sources_json
        )
        self.db.add(assistant_msg)
        self.db.commit()

        return session.session_token, rag_result
