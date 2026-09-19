import os
from typing import List
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    _model = None
    _model_name = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        if cls._model is None:
            cls._model_name = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            cls._model = SentenceTransformer(cls._model_name)
        return cls._model

    @classmethod
    def get_dimension(cls) -> int:
        model = cls.get_model()
        return model.get_sentence_embedding_dimension()

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        model = cls.get_model()
        # Returns a numpy array, convert to list for pgvector
        return model.encode(text).tolist()

    @classmethod
    def generate_embeddings_batch(cls, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = cls.get_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()
