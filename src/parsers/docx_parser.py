import io
import re
from typing import BinaryIO, List, Optional
import docx
from docx.text.paragraph import Paragraph

from src.db.models import NodeModel, generate_uuid

def _get_heading_level(paragraph: Paragraph) -> Optional[int]:
    style_name = paragraph.style.name if paragraph.style else ""
    match = re.match(r"^Heading\s+(\d+)$", style_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def parse_docx(file_stream: BinaryIO, document_id: str) -> List[NodeModel]:
    doc = docx.Document(file_stream)
    nodes: List[NodeModel] = []

    # Stack stores (heading_level, node_id) tuples to resolve hierarchical parent_id
    heading_stack: List[tuple[int, str]] = []
    current_order_index = 0

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue

        heading_level = _get_heading_level(paragraph)

        if heading_level is not None:
            while heading_stack and heading_stack[-1][0] >= heading_level:
                heading_stack.pop()

            parent_id = heading_stack[-1][1] if heading_stack else None
            node_id = generate_uuid()
            heading_stack.append((heading_level, node_id))

            nodes.append(
                NodeModel(
                    id=node_id,
                    document_id=document_id,
                    parent_id=parent_id,
                    node_type="header",
                    text_content=text,
                    order_index=current_order_index,
                    embedding_status="missing",
                )
            )
            current_order_index += 1
        else:
            parent_id = heading_stack[-1][1] if heading_stack else None
            nodes.append(
                NodeModel(
                    id=generate_uuid(),
                    document_id=document_id,
                    parent_id=parent_id,
                    node_type="paragraph",
                    text_content=text,
                    order_index=current_order_index,
                    embedding_status="missing",
                )
            )
            current_order_index += 1

    return nodes