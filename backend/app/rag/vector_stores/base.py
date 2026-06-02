from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseVectorStore(ABC):
    @abstractmethod
    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, **kwargs) -> List[str]:
        """Add texts with optional metadata to the vector store."""
        pass

    @abstractmethod
    def similarity_search(self, query: str, k: int = 4, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search the vector store for texts similar to the query."""
        pass

    @abstractmethod
    def delete_by_ids(self, ids: List[str]) -> bool:
        """Delete specific vectors by their IDs."""
        pass
    
    @abstractmethod
    def delete_by_filter(self, filter: Dict[str, Any]) -> bool:
        """Delete vectors matching a specific metadata filter (e.g. document_id)."""
        pass
