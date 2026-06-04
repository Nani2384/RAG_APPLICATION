import sys
import importlib.machinery
from unittest.mock import MagicMock

# Mock onnxruntime to prevent static import compatibility crashes on startup
mock_pkg = type('MockPackage', (MagicMock,), {
    '__path__': [],
    '__spec__': importlib.machinery.ModuleSpec('onnxruntime', None)
})()
sys.modules['onnxruntime'] = mock_pkg
sys.modules['onnxruntime.capi'] = mock_pkg
sys.modules['onnxruntime.capi._pybind_state'] = mock_pkg
sys.modules['onnxruntime.quantization'] = mock_pkg

from unstructured.partition.auto import partition
import os
import pdfplumber

class DocumentParser:
    def __init__(self):
        pass

    def parse_file(self, file_path: str) -> str:
        """Parses a file and returns aggregated text."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found.")
            
        _, ext = os.path.splitext(file_path.lower())
        if ext == ".pdf":
            # Lightweight PDF parsing using pdfplumber to bypass OCR/onnxruntime layout inference
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            return text
        else:
            elements = partition(filename=file_path)
            text = "\n".join([str(el) for el in elements if str(el).strip()])
            return text

