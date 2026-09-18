import re
import sqlite3
from typing import Any, Dict, List, Optional
import numpy as np

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

from backend.db.hierarchy import densify_order_indices, shift_order_indices
from backend.db.models import NodeModel, generate_uuid

def count_tokens(text: str) -> int:
    if not text or not text.strip():
        return 0
    words_and_symbols = re.findall(r"\w+|[^\w\s]", text)
    return max(1, int(len(words_and_symbols) * 1.25))

def split_text_into_sentences(text: str) -> List[Dict[str, Any]]:
    pattern = r'(?<=[.!?])\s+(?=[A-Z0-9"\'\n])|\n\n+'
    spans: List[Dict[str, Any]] = []
    last_end = 0
    for match in re.finditer(pattern, text):
        start, end = match.span()
        segment = text[last_end:start].strip()
        if segment:
            spans.append({"text": segment, "start": last_end, "end": start})
        last_end = end
    tail = text[last_end:].strip()
    if tail:
        spans.append({"text": tail, "start": last_end, "end": len(text)})
    return spans

def calculate_candidate_split_points(
    text: str,
    min_chunk_tokens: Optional[int] = None,
    max_chunk_tokens: Optional[int] = None,
    similarity_threshold: float = 0.65,
    min_chunk_char_length: Optional[int] = None,
    max_chunk_char_length: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if min_chunk_tokens is not None:
        effective_min_tokens = min_chunk_tokens
    elif min_chunk_char_length is not None:
        effective_min_tokens = max(10, min_chunk_char_length // 4)
    else:
        effective_min_tokens = 25

    if max_chunk_tokens is not None:
        effective_max_tokens = max_chunk_tokens
    elif max_chunk_char_length is not None:
        effective_max_tokens = max(effective_min_tokens + 10, max_chunk_char_length // 4)
    else:
        effective_max_tokens = 350

    sentences = split_text_into_sentences(text)
    total_tokens = count_tokens(text)
    if len(sentences) < 2 or total_tokens < effective_min_tokens * 1.5:
        return []

    split_proposals: List[Dict[str, Any]] = []
    accumulated_tokens = 0

    for i in range(len(sentences) - 1):
        s1 = sentences[i]
        s2 = sentences[i + 1]
        accumulated_tokens += count_tokens(s1["text"])

        w1 = set(re.findall(r"\w+", s1["text"].lower()))
        w2 = set(re.findall(r"\w+", s2["text"].lower()))

        union = w1.union(w2)
        jaccard = (len(w1.intersection(w2)) / len(union)) if union else 0.0

        is_semantic_shift = jaccard < similarity_threshold and accumulated_tokens >= effective_min_tokens
        is_length_exceeded = accumulated_tokens >= effective_max_tokens

        if is_semantic_shift or is_length_exceeded:
            boundary_pos = s1["end"]
            confidence = round(1.0 - jaccard, 3) if is_semantic_shift else 0.90
            split_proposals.append({
                "split_index": boundary_pos,
                "confidence": confidence,
                "token_count": accumulated_tokens,
                "before_snippet": s1["text"][-60:],
                "after_snippet": s2["text"][:60],
            })
            accumulated_tokens = 0

    return split_proposals

def create_sentence_preserving_splitter(chunk_size: int = 400, chunk_overlap: int = 40):
    if RecursiveCharacterTextSplitter is not None:
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", " "],
            keep_separator=True,
        )
    return None

def preview_semantic_splits_for_nodes(
    conn: sqlite3.Connection,
    node_ids: List[str],
    min_tokens: Optional[int] = None,
    max_tokens: Optional[int] = None,
) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in node_ids)
    cursor.execute(
        f"""
        SELECT id, document_id, parent_id, node_type, text_content, order_index
        FROM nodes
        WHERE id IN ({placeholders}) AND node_type = 'paragraph'
        ORDER BY order_index ASC;
        """,
        node_ids,
    )
    rows = cursor.fetchall()
    results = []

    for row in rows:
        text = row["text_content"] or ""
        splits = calculate_candidate_split_points(
            text,
            min_chunk_tokens=min_tokens,
            max_chunk_tokens=max_tokens,
        )
        slices = []
        last_idx = 0
        for sp in splits:
            cut = sp["split_index"]
            seg = text[last_idx:cut].strip()
            if seg:
                slices.append({"text": seg, "token_count": count_tokens(seg)})
            last_idx = cut
        tail = text[last_idx:].strip()
        if tail:
            slices.append({"text": tail, "token_count": count_tokens(tail)})

        results.append({
            "node_id": row["id"],
            "document_id": row["document_id"],
            "original_text": text,
            "total_tokens": count_tokens(text),
            "order_index": row["order_index"],
            "proposed_splits": splits,
            "proposed_slices": slices,
        })

    return results

def accept_semantic_split(
    conn: sqlite3.Connection,
    node_id: str,
    split_indices: List[int],
) -> List[NodeModel]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM nodes WHERE id = ? AND node_type = 'paragraph';",
        (node_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Paragraph node '{node_id}' not found")

    target = NodeModel(**dict(row))
    text = target.text_content or ""
    clean_indices = sorted(list(set(i for i in split_indices if 0 < i < len(text))))
    if not clean_indices:
        return [target]

    slices: List[str] = []
    last = 0
    for idx in clean_indices:
        slices.append(text[last:idx].strip())
        last = idx
    slices.append(text[last:].strip())
    slices = [s for s in slices if s]

    if len(slices) <= 1:
        return [target]

    new_slices_count = len(slices) - 1

    with conn:
        shift_order_indices(
            conn=conn,
            document_id=target.document_id,
            start_index=target.order_index + 1,
            delta=new_slices_count,
        )

        conn.execute("DELETE FROM node_metadata WHERE node_id = ?;", (target.id,))

        conn.execute(
            """
            UPDATE nodes
            SET text_content = ?, embedding_status = 'stale'
            WHERE id = ?;
            """,
            (slices[0], target.id),
        )

        created_nodes: List[NodeModel] = []
        first_node = NodeModel(
            id=target.id,
            document_id=target.document_id,
            parent_id=target.parent_id,
            node_type=target.node_type,
            text_content=slices[0],
            order_index=target.order_index,
            embedding_status="stale",
        )
        created_nodes.append(first_node)

        for i, slice_text in enumerate(slices[1:], start=1):
            new_node = NodeModel(
                id=generate_uuid(),
                document_id=target.document_id,
                parent_id=target.parent_id,
                node_type="paragraph",
                text_content=slice_text,
                order_index=target.order_index + i,
                embedding_status="missing",
            )
            conn.execute(
                """
                INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    new_node.id,
                    new_node.document_id,
                    new_node.parent_id,
                    new_node.node_type,
                    new_node.text_content,
                    new_node.order_index,
                    new_node.embedding_status,
                ),
            )
            created_nodes.append(new_node)

        densify_order_indices(conn, target.document_id)

    return created_nodes