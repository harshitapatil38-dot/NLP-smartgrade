"""
RAG Context Builder — Transforms semantic-search results into a
structured, length-limited context block for the LLM.

Architecture position:

    Question
        ↓
    Semantic Search (Step 5)   ← retrieves published chunks
        ↓
    **RAG Context Builder**    ← THIS module
        ↓
    RAG Service (Step 6C)      ← passes context + question to LLM

Responsibilities:
    • Accept the list of dicts returned by SemanticSearchService.search()
    • Format each result as a clearly separated, numbered SOURCE block
    • Preserve source metadata for later attribution
    • Enforce a configurable maximum context length
    • Return BOTH formatted text AND structured source metadata
    • Never call the LLM or the database directly

Non-responsibilities:
    • Does NOT perform semantic search
    • Does NOT call the LLM
    • Does NOT generate answers
    • Does NOT query the database
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Output data classes
# ---------------------------------------------------------------------------

@dataclass
class SourceReference:
    """Structured metadata for a single source used in the context."""
    document_id: int
    document_version_id: int
    chunk_id: int
    title: Optional[str]
    source: Optional[str]
    page_number: Optional[int]
    similarity_score: float
    department: Optional[str] = None


@dataclass
class RAGContext:
    """
    The complete output of the Context Builder.

    Attributes
    ----------
    context : str
        Formatted text block ready to be inserted into the LLM prompt.
        Empty string when no relevant results were found.
    sources : list[SourceReference]
        Ordered list of source metadata, one per chunk that made it
        into the context.  Empty list when no relevant results.
    chunk_count : int
        Number of chunks included in the context.
    truncated : bool
        True if context was cut short due to RAG_MAX_CONTEXT_LENGTH.
    """
    context: str = ""
    sources: List[SourceReference] = field(default_factory=list)
    chunk_count: int = 0
    truncated: bool = False


# ---------------------------------------------------------------------------
# Context Builder
# ---------------------------------------------------------------------------

class RAGContextBuilder:
    """
    Builds a formatted, length-bounded context block from semantic-search
    results.

    Configuration (environment variables):
        RAG_MAX_CONTEXT_LENGTH  — maximum character length of the formatted
                                  context block (default 4000)

    The builder does NOT duplicate the top-k or threshold logic already
    present in SemanticSearchService.  It trusts that the input has
    already been filtered to published, relevant chunks.  Its only
    additional safeguard is the hard context-length cap.
    """

    def __init__(
        self,
        max_context_length: Optional[int] = None,
    ):
        self.max_context_length = max_context_length or int(
            os.environ.get("RAG_MAX_CONTEXT_LENGTH", 4000)
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def build(self, search_results: List[Dict[str, Any]]) -> RAGContext:
        """
        Transform a list of semantic-search result dicts into a
        ``RAGContext``.

        Parameters
        ----------
        search_results :
            The list returned by ``SemanticSearchService.search()``.
            Each dict is expected to have at least:
            ``chunk_id``, ``document_id``, ``document_version_id``,
            ``text``, ``similarity_score``, ``title``.
            ``source``, ``page_number``, ``department``, ``metadata``
            are optional.

        Returns
        -------
        RAGContext
        """
        if not search_results:
            return RAGContext()

        sources: List[SourceReference] = []
        formatted_blocks: List[str] = []
        total_length = 0
        truncated = False

        for idx, result in enumerate(search_results, start=1):
            block = self._format_block(idx, result)

            # Enforce context-length cap
            if total_length + len(block) > self.max_context_length:
                truncated = True
                # Try to fit a partial block if we have room
                remaining = self.max_context_length - total_length
                if remaining > 100:  # only bother if there's meaningful room
                    formatted_blocks.append(block[:remaining] + "\n[...truncated]")
                break

            formatted_blocks.append(block)
            total_length += len(block)

            sources.append(self._extract_source(result))

        context_text = "\n\n".join(formatted_blocks)

        return RAGContext(
            context=context_text,
            sources=sources,
            chunk_count=len(sources),
            truncated=truncated,
        )

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _format_block(index: int, result: Dict[str, Any]) -> str:
        """
        Format a single search result as a numbered SOURCE block.

        Retrieved document text is treated strictly as *data*; it is
        placed inside a clearly delimited content section so the future
        system prompt can instruct the LLM to treat it accordingly.
        """
        lines = [f"SOURCE {index}"]

        title = result.get("title")
        if title:
            lines.append(f"Title: {title}")

        source = result.get("source")
        if source:
            lines.append(f"File: {source}")

        department = result.get("department")
        if department:
            lines.append(f"Department: {department}")

        page_number = result.get("page_number")
        if page_number is not None:
            lines.append(f"Page: {page_number}")

        similarity = result.get("similarity_score")
        if similarity is not None:
            lines.append(f"Relevance: {similarity:.2f}")

        # Separate metadata header from content with a blank line
        text = result.get("text", "")
        lines.append("")
        lines.append(text)

        return "\n".join(lines)

    @staticmethod
    def _extract_source(result: Dict[str, Any]) -> SourceReference:
        """Extract structured source metadata from a search-result dict."""
        return SourceReference(
            document_id=result["document_id"],
            document_version_id=result["document_version_id"],
            chunk_id=result["chunk_id"],
            title=result.get("title"),
            source=result.get("source"),
            page_number=result.get("page_number"),
            similarity_score=result.get("similarity_score", 0.0),
            department=result.get("department"),
        )
