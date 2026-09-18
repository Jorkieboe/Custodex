import io
import json
import re
import sqlite3
import zipfile
from typing import Any, Dict, List, Tuple

from backend.db.hierarchy import format_contextual_breadcrumb_string
from backend.db.models import SchemaFieldModel, generate_json_schema_from_fields
from backend.services.embedding_service import get_faiss_manager
from backend.services.validation_service import validate_project

class ValidationGateBlockedError(Exception):
    def __init__(self, validation_result: Dict[str, Any]):
        super().__init__("Project failed pre-export validation gate.")
        self.validation_result = validation_result

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name.strip().lower())
    return re.sub(r"[-\s]+", "_", cleaned) or "project"

def build_rag_bundle(conn: sqlite3.Connection, project_id: str) -> Tuple[bytes, str]:
    val_result = validate_project(conn, project_id)
    if not val_result["is_valid"]:
        raise ValidationGateBlockedError(val_result)

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects WHERE id = ?;", (project_id,))
    proj_row = cursor.fetchone()
    proj_name = proj_row["name"] if proj_row else "project"
    archive_slug = sanitize_filename(proj_name)

    cursor.execute(
        "SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC, id ASC;",
        (project_id,),
    )
    schema_fields = [SchemaFieldModel(**dict(r)) for r in cursor.fetchall()]
    schema_json_dict = generate_json_schema_from_fields(schema_fields)
    metadatascheme_str = json.dumps(schema_json_dict, indent=2)

    faiss_mgr = get_faiss_manager(project_id)
    faiss_mgr.sync_from_database(conn)
    faiss_bytes = faiss_mgr.serialize_faiss_bytes() or b""

    cursor.execute(
        """
        SELECT n.id, n.document_id, n.parent_id, n.text_content, n.order_index, d.filename
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.node_type = 'paragraph'
        ORDER BY d.order_index ASC, n.order_index ASC;
        """,
        (project_id,),
    )
    chunks = cursor.fetchall()

    field_map = {f.id: f.field_slug for f in schema_fields}

    db_metadata_entries: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        cid = chunk["id"]
        breadcrumb = format_contextual_breadcrumb_string(conn, cid)

        cursor.execute(
            "SELECT field_id, field_value FROM node_metadata WHERE node_id = ?;",
            (cid,),
        )
        meta_rows = cursor.fetchall()
        meta_dict: Dict[str, Any] = {}
        for mr in meta_rows:
            fid = mr["field_id"]
            slug = field_map.get(fid, fid)
            try:
                meta_dict[slug] = json.loads(mr["field_value"])
            except Exception:
                meta_dict[slug] = mr["field_value"]

        db_metadata_entries.append({
            "vector_index": idx,
            "chunk_id": cid,
            "document_id": chunk["document_id"],
            "document_name": chunk["filename"],
            "order_index": chunk["order_index"],
            "text_content": chunk["text_content"],
            "breadcrumb": breadcrumb,
            "metadata": meta_dict,
        })

    dbmetadata_str = json.dumps(db_metadata_entries, indent=2)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadatascheme.json", metadatascheme_str)
        zf.writestr("db.faiss", faiss_bytes)
        zf.writestr("dbmetadata.json", dbmetadata_str)

    zip_bytes = zip_buffer.getvalue()
    filename = f"{archive_slug}-rag-bundle.zip"
    return zip_bytes, filename