from unstructured.partition.auto import partition
import os

class DocumentParser:
    def __init__(self):
        pass

    def parse_file(self, file_path: str) -> str:
        """Parses a file and returns aggregated text via unstructured."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found.")
            
        elements = partition(filename=file_path)
        text = "\n".join([str(el) for el in elements if str(el).strip()])
        return text
