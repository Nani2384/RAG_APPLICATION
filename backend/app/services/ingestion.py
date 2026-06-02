import structlog
import json
from app.rag.document_loaders.loader import DocumentParser
from app.rag.chunkers.chunker import TokenChunker
from app.rag.embeddings.openai_embedder import OpenAIEmbedder
from app.rag.vector_stores.faiss_store import FAISSVectorStore
from app.rag.vector_stores.pinecone_store import PineconeVectorStore
from app.core.config import settings

logger = structlog.get_logger(__name__)

class IngestionService:
    def __init__(self):
        self.parser = DocumentParser()
        self.chunker = TokenChunker()
        self.embedder = OpenAIEmbedder()
        
        if settings.VECTOR_STORE_TYPE == "pinecone":
            self.vector_store = PineconeVectorStore(self.embedder)
        else:
            self.vector_store = FAISSVectorStore(self.embedder)

    def process_document(self, file_path: str, document_id: int, workspace_id: int):
        try:
            logger.info(f"Starting parsing for {file_path}")
            text = self.parser.parse_file(file_path)
            
            logger.info(f"Chunking document")
            chunks = self.chunker.chunk_text(text)
            
            metadatas = [{"document_id": document_id, "workspace_id": workspace_id, "chunk_index": i} for i in range(len(chunks))]
            
            logger.info(f"Embedding and indexing {len(chunks)} chunks")
            ids = self.vector_store.add_texts(texts=chunks, metadatas=metadatas)
            logger.info(f"Successfully indexed document {document_id}")
            return ids
        except Exception as e:
            logger.error(f"Failed to process document {document_id}", error=str(e))
            raise e
