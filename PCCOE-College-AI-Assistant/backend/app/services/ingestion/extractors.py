import pypdf
from docx import Document as DocxDocument
import io
from typing import List, Dict, Any

class ExtractionError(Exception):
    pass

class ExtractorService:
    @staticmethod
    def extract(file_path: str, ext: str) -> List[Dict[str, Any]]:
        """
        Returns a list of dictionaries with structure:
        {"text": extracted_text, "page_number": int or None}
        """
        try:
            if ext == 'pdf':
                return PDFExtractor.extract(file_path)
            elif ext == 'docx':
                return DOCXExtractor.extract(file_path)
            elif ext == 'txt':
                return TXTExtractor.extract(file_path)
            else:
                raise ExtractionError(f"Unsupported extension: {ext}")
        except Exception as e:
            raise ExtractionError(f"Extraction failed: {str(e)}")

class PDFExtractor:
    @staticmethod
    def extract(file_path: str) -> List[Dict[str, Any]]:
        extracted = []
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted.append({
                        "text": text,
                        "page_number": i + 1
                    })
        return extracted

class DOCXExtractor:
    @staticmethod
    def extract(file_path: str) -> List[Dict[str, Any]]:
        doc = DocxDocument(file_path)
        full_text = []
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)
        
        # DOCX doesn't have true pages easily accessible without rendering
        return [{"text": "\n".join(full_text), "page_number": None}]

class TXTExtractor:
    @staticmethod
    def extract(file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        return [{"text": text, "page_number": None}]
