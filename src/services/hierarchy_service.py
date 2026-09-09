import json
import sqlite3
from typing import Any, Dict, List, Optional
from src.db.hierarchy import (
    cascade_header_stale_status,
    densify_order_indices,
    shift_order_indices,
    validate_acyclic_parent,
)
from src.db.models import NodeModel, generate_uuid

def split_node(conn: sqlite3.Connection, node_id: str, top_text: str, bottom_text: str) -> tuple[NodeModel, NodeModel]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes WHERE id = ?;", (node_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Node with id {node_id} not found")

    original_doc_id = row["document_id"]
    original_parent_id = row["parent_id"]
    original_order_index = row["order_index"]
    original_status = row["embedding_status"]

    child_node_id = generate_uuid()
    child_order_index = original_order_index + 1

    with conn:
        # Shift downstream order indices
        shift_order_indices(conn, original_doc_id, start_index=child_order_index, delta=1)

        # Update upper slice
        new_primary_status = "stale" if original_status == "current" else original_status
        conn.execute(
            """
            UPDATE nodes
            SET text_content = ?, embedding_status = ?
            WHERE id = ?;
            """,
            (top_text, new_primary_status, node_id),
        )

        # Insert lower slice
        conn.execute(
            """
            INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status)
            VALUES (?, ?, ?, 'paragraph', ?, ?, 'missing');
            """,
            (child_node_id, original_doc_id, original_parent_id, bottom_text, child_order_index),
        )

        # Inherit metadata from parent chunk
        cursor.execute("SELECT field_id, field_value, user_edited FROM node_metadata WHERE node_id = ?;", (node_id,))
        metadata_rows = cursor.fetchall()
        for m in metadata_rows:
            conn.execute(
                """
                INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                VALUES (?, ?, ?, ?);
                """,
                (child_node_id, m["field_id"], m["field_value"], m["user_edited"]),
            )

    upper_node = NodeModel(
        id=node_id,
        document_id=original_doc_id,
        parent_id=original_parent_id,
        node_type=row["node_type"],
        text_content=top_text,
        order_index=original_order_index,
        embedding_status=new_primary_status,
    )
    lower_node = NodeModel(
        id=child_node_id,
        document_id=original_doc_id,
        parent_id=original_parent_id,
        node_type="paragraph",
        text_content=bottom_text,
        order_index=child_order_index,
        embedding_status="missing",
    )
    return (upper_node, lower_node)

def _combine_field_values(val1_raw: str, val2_raw: str) -> tuple[str, bool]:
    try:
        parsed1 = json.loads(val1_raw)
        parsed2 = json.loads(val2_raw)
    except Exception:
        if val1_raw == val2_raw:
            return (val1_raw, False)
        return (val1_raw, True)

    if parsed1 == parsed2:
        return (val1_raw, False)

    if isinstance(parsed1, list) and isinstance(parsed2, list):
        combined = []
        for item in parsed1 + parsed2:
            if item not in combined:
                combined.append(item)
        return (json.dumps(combined), False)

    # Conflicting scalar values: retain top chunk value and note conflict
    return (json.dumps({"value": parsed1, "conflict_with": parsed2, "has_conflict": True}), True)

def merge_nodes(conn: sqlite3.Connection, lead_node_id: str) -> NodeModel:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes WHERE id = ?;", (lead_node_id,))
    lead_row = cursor.fetchone()
    if not lead_row:
        raise ValueError(f"Lead node with id {lead_node_id} not found")

    doc_id = lead_row["document_id"]
    lead_order_index = lead_row["order_index"]

    cursor.execute(
        "SELECT * FROM nodes WHERE document_id = ? AND order_index = ?;",
        (doc_id, lead_order_index + 1),
    )
    succ_row = cursor.fetchone()
    if not succ_row:
        raise ValueError(f"No successor node found at order index {lead_order_index + 1}")

    succ_node_id = succ_row["id"]
    combined_text = lead_row["text_content"].rstrip() + "\n\n" + succ_row["text_content"].lstrip()

    # Combine metadata
    cursor.execute("SELECT field_id, field_value, user_edited FROM node_metadata WHERE node_id = ?;", (lead_node_id,))
    lead_meta = {r["field_id"]: (r["field_value"], bool(r["user_edited"])) for r in cursor.fetchall()}

    cursor.execute("SELECT field_id, field_value, user_edited FROM node_metadata WHERE node_id = ?;", (succ_node_id,))
    succ_meta = {r["field_id"]: (r["field_value"], bool(r["user_edited"])) for r in cursor.fetchall()}

    all_field_ids = set(lead_meta.keys()).union(set(succ_meta.keys()))
    final_metadata: Dict[str, tuple[str, bool]] = {}

    for fid in all_field_ids:
        if fid in lead_meta and fid in succ_meta:
            combined_val, _ = _combine_field_values(lead_meta[fid][0], succ_meta[fid][0])
            user_edited = lead_meta[fid][1] or succ_meta[fid][1]
            final_metadata[fid] = (combined_val, user_edited)
        elif fid in lead_meta:
            final_metadata[fid] = lead_meta[fid]
        else:
            final_metadata[fid] = succ_meta[fid]

    with conn:
        # Delete successor node (cascades metadata and embeddings)
        conn.execute("DELETE FROM nodes WHERE id = ?;", (succ_node_id,))

        # Update lead node
        new_status = "stale" if lead_row["embedding_status"] == "current" else lead_row["embedding_status"]
        conn.execute(
            """
            UPDATE nodes
            SET text_content = ?, embedding_status = ?
            WHERE id = ?;
            """,
            (combined_text, new_status, lead_node_id),
        )

        # Update metadata for lead node
        conn.execute("DELETE FROM node_metadata WHERE node_id = ?;", (lead_node_id,))
        for fid, (fval, uedit) in final_metadata.items():
            conn.execute(
                """
                INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                VALUES (?, ?, ?, ?);
                """,
                (lead_node_id, fid, fval, int(uedit)),
            )

        # Densify order indices across document
        densify_order_indices(conn, doc_id)

    return NodeModel(
        id=lead_node_id,
        document_id=doc_id,
        parent_id=lead_row["parent_id"],
        node_type=lead_row["node_type"],
        text_content=combined_text,
        order_index=lead_order_index,
        embedding_status=new_status,
    )

def promote_node_to_header(conn: sqlite3.Connection, node_id: str) -> NodeModel:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes WHERE id = ?;", (node_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Node with id {node_id} not found")

    doc_id = row["document_id"]
    current_order = row["order_index"]
    current_parent = row["parent_id"]

    # Subsequent sibling paragraphs that share current_parent get re-parented to this newly promoted header
    cursor.execute(
        """
        SELECT id, node_type, parent_id, order_index FROM nodes
        WHERE document_id = ? AND order_index > ?
        ORDER BY order_index ASC;
        """,
        (doc_id, current_order),
    )
    subsequent_nodes = cursor.fetchall()

    reparent_ids: List[str] = []
    for sn in subsequent_nodes:
        if sn["node_type"] == "header":
            break
        if sn["parent_id"] == current_parent:
            if not validate_acyclic_parent(conn, sn["id"], node_id):
                continue
            reparent_ids.append(sn["id"])

    with conn:
        conn.execute(
            """
            UPDATE nodes
            SET node_type = 'header', embedding_status = 'stale'
            WHERE id = ?;
            """,
            (node_id,),
        )

        if reparent_ids:
            placeholders = ",".join("?" * len(reparent_ids))
            conn.execute(
                f"""
                UPDATE nodes
                SET parent_id = ?, embedding_status = 'stale'
                WHERE id IN ({placeholders});
                """,
                [node_id] + reparent_ids,
            )

        cascade_header_stale_status(conn, node_id)

    return NodeModel(
        id=node_id,
        document_id=doc_id,
        parent_id=current_parent,
        node_type="header",
        text_content=row["text_content"],
        order_index=current_order,
        embedding_status="stale",
    )

def detach_selection_to_header(conn: sqlite3.Connection, node_id: str, selection_start: int, selection_end: int) -> List[NodeModel]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nodes WHERE id = ?;", (node_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Node with id {node_id} not found")

    full_text = row["text_content"]
    if selection_start < 0 or selection_end > len(full_text) or selection_start >= selection_end:
        raise ValueError("Invalid selection offsets")

    doc_id = row["document_id"]
    original_parent = row["parent_id"]
    base_order = row["order_index"]

    preceding_text = full_text[:selection_start].strip()
    header_text = full_text[selection_start:selection_end].strip()
    succeeding_text = full_text[selection_end:].strip()

    new_header_id = generate_uuid()
    created_nodes: List[NodeModel] = []

    with conn:
        if preceding_text:
            shift_order_indices(conn, doc_id, start_index=base_order + 1, delta=2 if succeeding_text else 1)

            conn.execute(
                "UPDATE nodes SET text_content = ?, embedding_status = 'stale' WHERE id = ?;",
                (preceding_text, node_id),
            )
            created_nodes.append(
                NodeModel(
                    id=node_id,
                    document_id=doc_id,
                    parent_id=original_parent,
                    node_type=row["node_type"],
                    text_content=preceding_text,
                    order_index=base_order,
                    embedding_status="stale",
                )
            )

            header_order = base_order + 1
            conn.execute(
                """
                INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status)
                VALUES (?, ?, ?, 'header', ?, ?, 'missing');
                """,
                (new_header_id, doc_id, original_parent, header_text, header_order),
            )
            created_nodes.append(
                NodeModel(
                    id=new_header_id,
                    document_id=doc_id,
                    parent_id=original_parent,
                    node_type="header",
                    text_content=header_text,
                    order_index=header_order,
                    embedding_status="missing",
                )
            )

            if succeeding_text:
                succ_id = generate_uuid()
                succ_order = header_order + 1
                conn.execute(
                    """
                    INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status)
                    VALUES (?, ?, ?, 'paragraph', ?, ?, 'missing');
                    """,
                    (succ_id, doc_id, new_header_id, succeeding_text, succ_order),
                )
                created_nodes.append(
                    NodeModel(
                        id=succ_id,
                        document_id=doc_id,
                        parent_id=new_header_id,
                        node_type="paragraph",
                        text_content=succeeding_text,
                        order_index=succ_order,
                        embedding_status="missing",
                    )
                )
        else:
            shift_order_indices(conn, doc_id, start_index=base_order + 1, delta=1 if succeeding_text else 0)

            conn.execute(
                """
                UPDATE nodes
                SET node_type = 'header', text_content = ?, embedding_status = 'stale'
                WHERE id = ?;
                """,
                (header_text, node_id),
            )
            created_nodes.append(
                NodeModel(
                    id=node_id,
                    document_id=doc_id,
                    parent_id=original_parent,
                    node_type="header",
                    text_content=header_text,
                    order_index=base_order,
                    embedding_status="stale",
                )
            )

            if succeeding_text:
                succ_id = generate_uuid()
                succ_order = base_order + 1
                conn.execute(
                    """
                    INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status)
                    VALUES (?, ?, ?, 'paragraph', ?, ?, 'missing');
                    """,
                    (succ_id, doc_id, node_id, succeeding_text, succ_order),
                )
                created_nodes.append(
                    NodeModel(
                        id=succ_id,
                        document_id=doc_id,
                        parent_id=node_id,
                        node_type="paragraph",
                        text_content=succeeding_text,
                        order_index=succ_order,
                        embedding_status="missing",
                    )
                )

        densify_order_indices(conn, doc_id)

    return created_nodes