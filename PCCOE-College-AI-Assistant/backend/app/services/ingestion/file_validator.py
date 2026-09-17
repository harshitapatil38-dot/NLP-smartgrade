import os

class FileValidationError(Exception):
    pass

class FileValidator:
    def __init__(self, allowed_extensions=None, max_size_mb=10):
        self.allowed_extensions = allowed_extensions or ['pdf', 'docx', 'txt']
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def validate(self, filename: str, file_content: bytes):
        if not file_content:
            raise FileValidationError("File is empty.")

        if len(file_content) > self.max_size_bytes:
            raise FileValidationError(f"File size exceeds maximum allowed size ({self.max_size_bytes / 1024 / 1024} MB).")

        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if ext not in self.allowed_extensions:
            raise FileValidationError(f"Unsupported file extension: {ext}. Allowed: {self.allowed_extensions}")

        return True
