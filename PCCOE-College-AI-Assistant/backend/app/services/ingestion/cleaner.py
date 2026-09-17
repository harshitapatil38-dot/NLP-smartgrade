import re

class TextCleaner:
    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        
        # Replace multiple spaces with a single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Replace multiple newlines with a double newline (preserve paragraphs)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        
        # Remove null characters and other unprintable weirdness safely
        text = text.replace('\x00', '')
        
        # Strip leading/trailing whitespace
        return text.strip()
