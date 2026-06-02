import faiss
import numpy as np
import uuid
import json
import os
from typing import List, Dict, Any, Optional
from app.rag.vector_stores.base import BaseVectorStore
from app.core.config import settings

class FAISSVectorStore(BaseVectorStore):
    def __init__(self, embedder, index_path: str = "/app/storage/faiss_index"):
        self.embedder = embedder
        self.index_path = index_path
        self.dimension = 1536 # OpenAI default for small
        self.index = None
        self.docstore = {} # ID to chunk mapping
        self._load_or_create_index()

    def _load_or_create_index(self):
        if os.path.exists(self.index_path + ".index"):
            self.index = faiss.read_index(self.index_path + ".index")
            with open(self.index_path + ".json", "r") as f:
                self.docstore = json.load(f)
        else:
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            self.index = faiss.IndexFlatL2(self.dimension)
            self.docstore = {}

    def _save_index(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path + ".index")
        with open(self.index_path + ".json", "w") as f:
            json.dump(self.docstore, f)

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, **kwargs) -> List[str]:
        if not texts:
            return []
        
        embeddings = self.embedder.embed_documents(texts)
        ids = [str(uuid.uuid4()) for _ in texts]
        
        vectors = np.array(embeddings).astype("float32")
        self.index.add(vectors)

        for i, text in enumerate(texts):
            doc_id = ids[i]
            meta = metadatas[i] if metadatas else {}
            self.docstore[doc_id] = {
                "text": text,
                "metadata": meta,
                "index_id": self.index.ntotal - len(texts) + i
            }
            
        self._save_index()
        return ids

    def similarity_search(self, query: str, k: int = 4, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
            
        query_embedding = self.embedder.embed_query(query)
        vector = np.array([query_embedding]).astype("float32")
        
        # We retrieve more than k if we need to filter
        search_k = k * 3 if filter else k
        distances, indices = self.index.search(vector, search_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            
            # Find the document by index (naive search for FAISS representation)
            # In a real app we would use an IndexIDMap but keeping it simple with dict scan
            for doc_id, doc in self.docstore.items():
                if doc["index_id"] == idx:
                    # Apply filter
                    if filter:
                        match = all(doc["metadata"].get(k) == v for k, v in filter.items())
                        if not match:
                            continue
                            
                    results.append({
                        "id": doc_id,
                        "text": doc["text"],
                        "metadata": doc["metadata"],
                        "score": float(distances[0][i])
                    })
                    break
            
            if len(results) >= k:
                break
                
        return results

    def delete_by_ids(self, ids: List[str]) -> bool:
        if not ids:
            return True
            
        removed_any = False
        for doc_id in ids:
            if doc_id in self.docstore:
                del self.docstore[doc_id]
                removed_any = True
                
        if not removed_any:
            return True
            
        # Rebuild Index to avoid index-shift mappings corruption
        self.index = faiss.IndexFlatL2(self.dimension)
        
        if not self.docstore:
            self._save_index()
            return True
            
        remaining_ids = list(self.docstore.keys())
        remaining_docs = [self.docstore[doc_id] for doc_id in remaining_ids]
        remaining_texts = [doc["text"] for doc in remaining_docs]
        
        # Embed remaining text chunks again
        embeddings = self.embedder.embed_documents(remaining_texts)
        vectors = np.array(embeddings).astype("float32")
        
        # Add to FAISS index
        self.index.add(vectors)
        
        # Update sequential index IDs inside docstore map
        for i, doc_id in enumerate(remaining_ids):
            self.docstore[doc_id]["index_id"] = i
            
        self._save_index()
        return True

    def delete_by_filter(self, filter: Dict[str, Any]) -> bool:
        return True
