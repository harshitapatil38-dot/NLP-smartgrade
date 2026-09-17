from typing import List, Dict, Any

class TextChunker:
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Takes a list of dictionaries with {"text": str, "page_number": int|None}.
        Returns chunks with metadata retaining the page number.
        """
        chunks = []
        global_chunk_idx = 0

        for page in pages:
            text = page.get("text", "")
            page_num = page.get("page_number")
            
            # Simple sliding window chunker by character
            # A more robust one might split by paragraphs/sentences first.
            start = 0
            text_length = len(text)

            while start < text_length:
                end = start + self.chunk_size
                
                # If we're not at the end of the text, try to find a nice boundary
                if end < text_length:
                    # Look for a newline or period within the last 100 chars of the chunk
                    boundary = max(
                        text.rfind('\n', start, end),
                        text.rfind('. ', start, end)
                    )
                    # If a sensible boundary exists and isn't too far back, use it
                    if boundary != -1 and boundary > start + (self.chunk_size // 2):
                        end = boundary + 1 # Include the boundary char

                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "chunk_order": global_chunk_idx,
                        "chunk_text": chunk_text,
                        "metadata_": {"page_number": page_num} if page_num else {}
                    })
                    global_chunk_idx += 1
                
                # Move start forward, accounting for overlap
                start = end - self.overlap
                
                # Prevent infinite loops if boundary calculation gets stuck
                if start >= end:
                    start = end

        return chunks
