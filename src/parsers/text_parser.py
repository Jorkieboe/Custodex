import re
from typing import List, Optional
from src.db.models import NodeModel, generate_uuid

def parse_markdown(text_content: str, document_id: str) -> List[NodeModel]:
    nodes: List[NodeModel] = []
    lines = text_content.splitlines()
    heading_stack: List[tuple[int, str]] = []
    current_order_index = 0
    buffer: List[str] = []

    def flush_buffer():
        nonlocal current_order_index
        if buffer:
            paragraph_text = "\n".join(buffer).strip()
            if paragraph_text:
                parent_id = heading_stack[-1][1] if heading_stack else None
                nodes.append(
                    NodeModel(
                        id=generate_uuid(),
                        document_id=document_id,
                        parent_id=parent_id,
                        node_type="paragraph",
                        text_content=paragraph_text,
                        order_index=current_order_index,
                        embedding_status="missing",
                    )
                )
                current_order_index += 1
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            flush_buffer()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            if heading_text:
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                parent_id = heading_stack[-1][1] if heading_stack else None
                node_id = generate_uuid()
                heading_stack.append((level, node_id))
                nodes.append(
                    NodeModel(
                        id=node_id,
                        document_id=document_id,
                        parent_id=parent_id,
                        node_type="header",
                        text_content=heading_text,
                        order_index=current_order_index,
                        embedding_status="missing",
                    )
                )
                current_order_index += 1
        elif not stripped:
            flush_buffer()
        else:
            buffer.append(stripped)

    flush_buffer()
    return nodes

def parse_plain_text(text_content: str, document_id: str) -> List[NodeModel]:
    nodes: List[NodeModel] = []
    raw_blocks = re.split(r"\n\s*\n+", text_content)
    current_order_index = 0

    for block in raw_blocks:
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