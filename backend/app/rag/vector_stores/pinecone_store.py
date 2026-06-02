from typing import List, Dict, Any, Optional
import uuid
from pinecone import Pinecone
from app.rag.vector_stores.base import BaseVectorStore
from app.core.config import settings

class PineconeVectorStore(BaseVectorStore):
    def __init__(self, embedder):
        self.embedder = embedder
        if not settings.PINECONE_API_KEY:
            raise ValueError("Pinecone API key must be provided.")
            
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = self.pc.Index(settings.PINECONE_INDEX_NAME)

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, **kwargs) -> List[str]:
        if not texts:
            return []
            
        embeddings = self.embedder.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in texts]
        
        vectors = []
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas else {}
            meta["text"] = text # Store the text in metadata
            
            vectors.append({
                "id": ids[i],
                "values": embeddings[i],
                "metadata": meta
            })
            
        # Pinecone max batch size is usually 1000, batched insert logic here if needed
        self.index.upsert(vectors=vectors)
        return ids

    def similarity_search(self, query: str, k: int = 4, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query_embedding = self.embedder.embed_query(query)
        
        response = self.index.query(
            vector=query_embedding,
            top_k=k,
            filter=filter,
            include_metadata=True
        )
        
        results = []
        for match in response.matches:
            results.append({
                "id": match.id,
                "text": match.metadata.get("text", ""),
                "metadata": {k: v for k, v in match.metadata.items() if k != "text"},
                "score": match.score
            })
            
        return results

    def delete_by_ids(self, ids: List[str]) -> bool:
        self.index.delete(ids=ids)
        return True

    def delete_by_filter(self, filter: Dict[str, Any]) -> bool:
        self.index.delete(filter=filter)
        return True
