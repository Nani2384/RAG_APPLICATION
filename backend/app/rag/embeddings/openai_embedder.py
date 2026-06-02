from typing import List, Optional
from openai import OpenAI
from app.core.config import settings

class OpenAIEmbedder:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
        self.model = settings.DEFAULT_EMBEDDING_MODEL
        self._local_model = None

    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            import structlog
            logger = structlog.get_logger(__name__)
            logger.info("Initializing local SentenceTransformer model 'all-MiniLM-L6-v2' as RAG fallback...")
            self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Local SentenceTransformer initialized successfully.")
        return self._local_model

    def _embed_locally(self, texts: List[str]) -> List[List[float]]:
        model = self._get_local_model()
        embeddings = model.encode(texts)
        
        # Pad 384-dimensional local embeddings to 1536 dimensions to match FAISS dimension config
        padded_embeddings = []
        for emb in embeddings:
            emb_list = list(emb)
            if len(emb_list) < 1536:
                emb_list += [0.0] * (1536 - len(emb_list))
            padded_embeddings.append(emb_list[:1536])
        return padded_embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            return self._embed_locally(texts)
        try:
            response = self.client.embeddings.create(input=texts, model=self.model)
            return [data.embedding for data in response.data]
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warn("OpenAI embed_documents failed, falling back to local SentenceTransformers", error=str(e))
            return self._embed_locally(texts)

    def embed_query(self, text: str) -> List[float]:
        if not self.client:
            return self._embed_locally([text])[0]
        try:
            response = self.client.embeddings.create(input=[text], model=self.model)
            return response.data[0].embedding
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warn("OpenAI embed_query failed, falling back to local SentenceTransformers", error=str(e))
            return self._embed_locally([text])[0]
