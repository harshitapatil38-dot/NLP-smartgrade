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
        3. Handles greetings/help deterministically.
        4. Contextualizes follow-up queries using LLM.
        5. Calls RAG service with contextualized query.
        6. Saves messages to the database.
        """
        # 1. Get or create session
        session = self.get_or_create_session(session_token)

        # 2. Get formatted history (BEFORE adding current message)
        history_str = self.get_chat_history(session.id)

        # 3. Save user message first so we have a record
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=question
        )
        self.db.add(user_msg)
        self.db.commit()

        # Handle simple greetings deterministically
        q_lower = question.lower().strip()
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "help"}
        if q_lower in greetings or q_lower.startswith(("hi ", "hello ", "hey ")):
            welcome_msg = (
                "Hello! I am the official PCCOE College Information Assistant. "
                "I can help you with questions about admissions, departments, courses, "
                "library, facilities, scholarships, clubs, and other official college information. "
                "How can I help you today?"
            )
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=welcome_msg,
                retrieved_sources=[]
            )
            self.db.add(assistant_msg)
            self.db.commit()
            return session.session_token, RAGResult(
                answer=welcome_msg,
                sources=[],
                query=question,
                retrieved_chunks=0,
                context_truncated=False
            )
        
        # 4. Contextualize follow-up query if history exists
        search_query = question
        if history_str:
            try:
                from app.services.llm_service import LLMService
                provider = LLMService.get_provider()
                sys_prompt = (
                    "Given the conversation history, rewrite the user's latest question to be a standalone query "
                    "that includes all necessary context (e.g., resolving pronouns like 'it' or 'they'). "
                    "If the latest question is completely ambiguous and lacks any context (e.g., 'What are the timings?' "
                    "with no prior mention of a specific facility), simply reply with the exact word: AMBIGUOUS. "
                    "Otherwise, reply ONLY with the rewritten standalone query, with no additional text."
                )
                user_prompt = f"History:\n{history_str}\n\nLatest Question: {question}"
                rewritten = provider.generate(
                    system_prompt=sys_prompt,
                    user_question=user_prompt,
                    context="",
                    max_tokens=50
                ).strip()
                
                if rewritten == "AMBIGUOUS":
                    clarification = "Could you specify which area you mean—for example, the library, college, or another service?"
                    assistant_msg = ChatMessage(
                        session_id=session.id,
                        role="assistant",
                        content=clarification,
                        retrieved_sources=[]
                    )
                    self.db.add(assistant_msg)
                    self.db.commit()
                    return session.session_token, RAGResult(
                        answer=clarification,
                        sources=[],
                        query=question,
                        retrieved_chunks=0,
                        context_truncated=False
                    )
                elif rewritten and len(rewritten) > 3:
                    search_query = rewritten
            except Exception:
                pass # Fallback to original question on LLM error

        # Catch ambiguous questions without history
        elif len(q_lower.split()) <= 4 and ("timing" in q_lower or "where" in q_lower or "how much" in q_lower):
            # Very simplistic heuristic for generic questions without context
            if "library" not in q_lower and "college" not in q_lower and "admission" not in q_lower:
                clarification = "Could you specify which area you mean—for example, the library, college, or another service?"
                assistant_msg = ChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content=clarification,
                    retrieved_sources=[]
                )
                self.db.add(assistant_msg)
                self.db.commit()
                return session.session_token, RAGResult(
                    answer=clarification,
                    sources=[],
                    query=question,
                    retrieved_chunks=0,
                    context_truncated=False
                )

        # 5. Perform RAG query
        # We pass search_query to search, but want original question (or rewritten) for final prompt.
        # Actually RAGService currently takes question and history_str. Let's update RAGService to accept a standalone_query.
        # Wait, if we rewrite it here, we can just pass the rewritten query to rag_service.ask.
        rag_result = self.rag_service.ask(search_query, conversation_history=history_str, original_question=question)

        # 6. Save assistant message
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
