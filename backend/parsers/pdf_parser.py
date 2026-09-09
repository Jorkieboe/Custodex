import io
import re
from typing import BinaryIO, List
from backend.db.models import NodeModel, generate_uuid

def parse_pdf_fallback(file_stream: BinaryIO, document_id: str) -> List[NodeModel]:
    raw_bytes = file_stream.read()
    text_parts: List[str] = []

    bt_blocks = re.findall(rb"BT[\s\S]*?ET", raw_bytes)
    for block in bt_blocks:
        strings = re.findall(rb"\((.*?)\)", block)
        for s in strings:
            try:
                decoded = s.decode("utf-8", errors="ignore").strip()
                if decoded:
                    text_parts.append(decoded)
            except Exception:
                continue

    extracted_text = " ".join(text_parts).strip()
    if not extracted_text:
        ascii_strings = re.findall(rb"[A-Za-z0-9 ,.;:!?'\"()\n\r-]{4,}", raw_bytes)
        decoded_blocks = [
            b.decode("latin-1", errors="ignore").strip()
            for b in ascii_strings
            if not b.startswith(rb"/") and not b.startswith(rb"end")
        ]
        extracted_text = "\n\n".join(decoded_blocks)

    if not extracted_text:
        extracted_text = "PDF document text could not be extracted."

    blocks = re.split(r"\n\s*\n+", extracted_text)
    nodes: List[NodeModel] = []
    current_order_index = 0

    for block in blocks:
        clean = block.strip()
        if not clean:
            continue
        nodes.append(
            NodeModel(
                id=generate_uuid(),
                document_id=document_id,
                parent_id=None,
                node_type="paragraph",
                text_content=clean,
                order_index=current_order_index,
                embedding_status="missing",
            )
        )
        current_order_index += 1

    return nodes