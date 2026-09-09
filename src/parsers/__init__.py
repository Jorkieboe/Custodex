import io
from pathlib import Path
from typing import BinaryIO, List
from src.db.models import NodeModel
from src.parsers.docx_parser import parse_docx
from src.parsers.text_parser import parse_markdown, parse_plain_text
from src.parsers.pdf_parser import parse_pdf_fallback

def parse_document_file(file_stream: BinaryIO, filename: str, document_id: str) -> List[NodeModel]:
    ext = Path(filename).suffix.lower()
    if ext == ".docx":
        return parse_docx(file_stream, document_id)
    elif ext in [".md", ".markdown"]:
        content = file_stream.read().decode("utf-8", errors="replace")
        return parse_markdown(content, document_id)
    elif ext in [".txt", ".text"]:
        content = file_stream.read().decode("utf-8", errors="replace")
        return parse_plain_text(content, document_id)
    elif ext == ".pdf":
        return parse_pdf_fallback(file_stream, document_id)
    else:
        content = file_stream.read().decode("utf-8", errors="replace")
        return parse_plain_text(content, document_id)