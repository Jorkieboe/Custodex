import json
import re
import sqlite3
from typing import Any, Dict, List, Optional

try:
    from backend.db.models import SchemaFieldModel
except ImportError:
    from src.db.models import SchemaFieldModel

ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def is_valid_type(val: Any, field_type: str) -> bool:
    if val is None:
        return True
    if field_type == "string":
        return isinstance(val, str)
    if field_type == "number":
        return type(val) in (int, float) and not isinstance(val, bool)
    if field_type == "boolean":
        return isinstance(val, bool)
    if field_type == "date":
        return isinstance(val, str) and bool(ISO_DATE_REGEX.match(val.strip()))
    if field_type == "array[string]":
        return isinstance(val, list) and all(isinstance(item, str) for item in val)
    if field_type == "array[number]":
        return isinstance(val, list) and all(
            type(item) in (int, float) and not isinstance(item, bool) for item in val
        )
    return True

def validate_project(conn: sqlite3.Connection, project_id: str) -> Dict[str, Any]:
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT n.id, n.document_id, n.parent_id, n.text_content, n.order_index,
               n.embedding_status, d.filename
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.node_type = 'paragraph'
        ORDER BY d.order_index ASC, n.order_index ASC;
        """,
        (project_id,),
    )
    chunks = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC, id ASC;",
        (project_id,),
    )
    schema_fields = [SchemaFieldModel(**dict(r)) for r in cursor.fetchall()]

    chunk_ids = [c["id"] for c in chunks]
    metadata_by_chunk: Dict[str, Dict[str, Any]] = {cid: {} for cid in chunk_ids}

    if chunk_ids:
        placeholders = ",".join("?" for _ in chunk_ids)
        cursor.execute(
            f"""
            SELECT node_id, field_id, field_value, user_edited
            FROM node_metadata
            WHERE node_id IN ({placeholders});
            """,
            chunk_ids,
        )
        for row in cursor.fetchall():
            try:
                parsed_val = json.loads(row["field_value"])
            except Exception:
                parsed_val = row["field_value"]
            metadata_by_chunk[row["node_id"]][row["field_id"]] = {
                "value": parsed_val,
                "user_edited": bool(row["user_edited"]),
            }

    blockers: List[Dict[str, Any]] = []

    for chunk in chunks:
        cid = chunk["id"]
        text = chunk["text_content"] or ""
        doc_id = chunk["document_id"]
        filename = chunk["filename"]

        # Rule 1: No chunk contains empty or whitespace-only text
        if not text.strip():
            blockers.append({
                "rule": "empty_chunk",
                "node_id": cid,
                "document_id": doc_id,
                "filename": filename,
                "message": "Chunk contains empty or whitespace-only text content.",
                "remediation": "Edit this chunk to add text or delete it in the Chunk Canvas step.",
            })

        # Rule 2: No chunk has embedding_status != 'current'
        emb_status = chunk["embedding_status"]
        if emb_status != "current":
            blockers.append({
                "rule": "uncalculated_embedding",
                "node_id": cid,
                "document_id": doc_id,
                "filename": filename,
                "message": f"Chunk embedding status is '{emb_status}' (must be 'current').",
                "remediation": "Refresh embeddings in the Embedding Refresh step.",
            })

        # Rule 3: All chunk metadata validates strictly against the active schema
        chunk_meta = metadata_by_chunk.get(cid, {})

        for field in schema_fields:
            field_entry = chunk_meta.get(field.id) or chunk_meta.get(field.field_slug)
            field_val = field_entry["value"] if field_entry else None

            # Check for unresolved merge conflicts
            if isinstance(field_val, dict) and field_val.get("has_conflict") is True:
                blockers.append({
                    "rule": "schema_violation",
                    "node_id": cid,
                    "document_id": doc_id,
                    "filename": filename,
                    "field_id": field.id,
                    "field_slug": field.field_slug,
                    "message": f"Field '{field.field_label}' contains an unresolved merge conflict.",
                    "remediation": "Inspect and resolve conflicting values in the Metadata Inspector.",
                })
                continue

            # Check required fields
            if field.is_required:
                is_empty = (
                    field_val is None
                    or (isinstance(field_val, str) and not field_val.strip())
                    or (isinstance(field_val, list) and len(field_val) == 0)
                )
                if is_empty:
                    blockers.append({
                        "rule": "schema_violation",
                        "node_id": cid,
                        "document_id": doc_id,
                        "filename": filename,
                        "field_id": field.id,
                        "field_slug": field.field_slug,
                        "message": f"Required metadata field '{field.field_label}' is missing or empty.",
                        "remediation": f"Populate the '{field.field_label}' field using metadata extraction or manual editing.",
                    })
                    continue

            # Check type constraints
            if field_val is not None:
                if not is_valid_type(field_val, field_type=field.field_type):
                    blockers.append({
                        "rule": "schema_violation",
                        "node_id": cid,
                        "document_id": doc_id,
                        "filename": filename,
                        "field_id": field.id,
                        "field_slug": field.field_slug,
                        "message": f"Field '{field.field_label}' has value incompatible with type '{field.field_type}'.",
                        "remediation": f"Correct the value to match the expected '{field.field_type}' type.",
                    })

    empty_count = sum(1 for b in blockers if b["rule"] == "empty_chunk")
    embedding_count = sum(1 for b in blockers if b["rule"] == "uncalculated_embedding")
    schema_count = sum(1 for b in blockers if b["rule"] == "schema_violation")

    return {
        "is_valid": len(blockers) == 0,
        "total_chunks": len(chunks),
        "total_blockers": len(blockers),
        "blockers": blockers,
        "summary": {
            "empty_chunks": empty_count,
            "uncalculated_embeddings": embedding_count,
            "schema_violations": schema_count,
        },
    }