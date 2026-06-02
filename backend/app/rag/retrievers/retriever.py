from typing import List, Dict, Any
from app.rag.vector_stores.base import BaseVectorStore

class RAGRetriever:
    def __init__(self, vector_store: BaseVectorStore):
        self.vector_store = vector_store

    def retrieve(self, query: str, workspace_id: int, top_k: int = 4) -> List[Dict[str, Any]]:
        import re
        
        # 1. Retrieve candidates (top_k * 3) to have a pool for hybrid re-ranking
        filter_dict = {"workspace_id": workspace_id}
        candidates = self.vector_store.similarity_search(query=query, k=top_k * 3, filter=filter_dict)
        
        if not candidates:
            return []
            
        # 2. Extract unique query keywords (len > 3, exclude common stopwords)
        stopwords = {"what", "how", "why", "where", "when", "who", "which", "whose", "whom", "this", "that", "these", "those", "their", "there", "here", "with", "from", "into", "onto", "then", "than", "does", "been", "have", "were", "should", "would", "could", "about"}
        keywords = [
            w.lower() for w in re.findall(r'\w+', query)
            if len(w) > 3 and w.lower() not in stopwords
        ]
        unique_keywords = list(set(keywords))
        
        # 3. Compute Lexical-Semantic Hybrid Scores
        re_ranked = []
        for chunk in candidates:
            text_lower = chunk["text"].lower()
            
            # Count exact matches for unique query keywords
            matches = sum(1 for kw in unique_keywords if kw in text_lower)
            density = matches / len(unique_keywords) if unique_keywords else 0.0
            
            # FAISS distance is Index L2 (smaller is better).
            # We subtract the keyword density factor to lower (improve) the L2 score.
            # Semantic weight: 0.7, Lexical weight: 0.3 (lower score is better match)
            hybrid_score = (chunk["score"] * 0.7) - (density * 0.3)
            
            chunk_copy = dict(chunk)
            chunk_copy["hybrid_score"] = float(hybrid_score)
            chunk_copy["keyword_matches"] = matches
            re_ranked.append(chunk_copy)
            
        # 4. Sort ascending by hybrid_score (smallest distance/score is best)
        re_ranked.sort(key=lambda x: x["hybrid_score"])
        
        # 5. Return top_k elements
        return re_ranked[:top_k]
