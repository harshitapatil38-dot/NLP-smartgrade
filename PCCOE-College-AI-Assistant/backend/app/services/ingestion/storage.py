import os
import uuid
from typing import BinaryIO

class StorageService:
    def save_file(self, filename: str, content: bytes) -> str:
        raise NotImplementedError

class LocalStorageService(StorageService):
    def __init__(self, base_dir: str = "./storage"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save_file(self, filename: str, content: bytes) -> str:
        # Generate safe internal filename
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        internal_filename = f"{uuid.uuid4().hex}.{ext}"
        
        file_path = os.path.join(self.base_dir, internal_filename)
        
        with open(file_path, 'wb') as f:
            f.write(content)
            
        return file_path
