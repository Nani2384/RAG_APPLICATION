import tiktoken
from typing import List

class TokenChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50, model_name: str = "gpt-4o"):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        try:
            self.tokenizer = tiktoken.encoding_for_model(model_name)
        except Exception:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk_text(self, text: str) -> List[str]:
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        i = 0
        while i < len(tokens):
            # Take a slice of tokens
            chunk_tokens = tokens[i : i + self.chunk_size]
            chunks.append(self.tokenizer.decode(chunk_tokens))
            
            # Move forward by chunk_size - overlap, to keep some overlap
            i += self.chunk_size - self.chunk_overlap
            
        return chunks
