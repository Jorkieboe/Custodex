import io
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from src.db.models import DocumentModel, NodeModel, generate_uuid
from src.parsers import parse_document_file
from src.services.project_manager import get_project_connection, ensure_project_record

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])

class DocumentSummary(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    order_index: int
    total_nodes: int
    current_embeddings: int
    stale_embeddings: int
    missing_embeddings: int

class ReorderDocumentsPayload(BaseModel):
    document_ids: List[str]

@router.post("/upload", response_model=List[DocumentSummary])
async def upload_documents(project_id: str, files: List[UploadFile] = File(...)):
    conn = get_project_connection(project_id)
    ensure_project_record(conn, project_id)

    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(order_index), -1) as max_order FROM documents WHERE project_id = ?;", (project_id,))
    current_max_order = cursor.fetchone()["max_order"]

    summaries: List[DocumentSummary] = []

    for file in files:
        current_max_order += 1
        doc_id = generate_uuid()
        filename = file.filename or f"document_{doc_id}.txt"
        file_ext = Path(filename).suffix.lstrip(".").lower() or "txt"

        content_bytes = await file.read()
        file_stream = io.BytesIO(content_bytes)
        parsed_nodes = parse_document_file(file_stream, filename, doc_id)

        with conn:
            conn.execute(
                """
                INSERT INTO documents (id, project_id, filename, file_type, order_index)
                VALUES (?, ?, ?, ?, ?);
                """,
                (doc_id, project_id, filename, file_ext, current_max_order),
            )

            for node in parsed_nodes:
                conn.execute(
                    """
                    INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (node.id, node.document_id, node.parent_id, node.node_type, node.text_content, node.order_index, node.embedding_status),
                )

        summaries.append(
            DocumentSummary(
                id=doc_id,
                project_id=project_id,
                filename=filename,
                file_type=file_ext,
                order_index=current_max_order,
                total_nodes=len(parsed_nodes),
                current_embeddings=0,
                stale_embeddings=0,
                missing_embeddings=len(parsed_nodes),
            )
        )

    return summaries

@router.get("", response_model=List[DocumentSummary])
async def get_documents(project_id: str):
    conn = get_project_connection(project_id)
    ensure_project_record(conn, project_id)

    query = """
    SELECT
        d.id, d.project_id, d.filename, d.file_type, d.order_index,
        COUNT(n.id) as total_nodes,
        COALESCE(SUM(CASE WHEN n.embedding_status = 'current' THEN 1 ELSE 0 END), 0) as current_embeddings,
        COALESCE(SUM(CASE WHEN n.embedding_status = 'stale' THEN 1 ELSE 0 END), 0) as stale_embeddings,
        COALESCE(SUM(CASE WHEN n.embedding_status = 'missing' THEN 1 ELSE 0 END), 0) as missing_embeddings
    FROM documents d
    LEFT JOIN nodes n ON d.id = n.document_id
    WHERE d.project_id = ?
    GROUP BY d.id
    ORDER BY d.order_index ASC;
    """
    cursor = conn.cursor()
    cursor.execute(query, (project_id,))
    rows = cursor.fetchall()
    return [DocumentSummary(**dict(r)) for r in rows]

@router.delete("/{doc_id}")
async def delete_document(project_id: str, doc_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM documents WHERE id = ? AND project_id = ?;", (doc_id, project_id))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Document not found")

    with conn:
        conn.execute("DELETE FROM documents WHERE id = ?;", (doc_id,))

        cursor.execute(
            "SELECT id FROM documents WHERE project_id = ? ORDER BY order_index ASC;",
            (project_id,),
        )
        remaining = cursor.fetchall()
        for idx, row in enumerate(remaining):
            conn.execute("UPDATE documents SET order_index = ? WHERE id = ?;", (idx, row["id"]))

    return {"status": "deleted", "document_id": doc_id}

@router.patch("/reorder")
async def reorder_documents(project_id: str, payload: ReorderDocumentsPayload):
    conn = get_project_connection(project_id)
    with conn:
        for idx, doc_id in enumerate(payload.document_ids):
            conn.execute(
                "UPDATE documents SET order_index = ? WHERE id = ? AND project_id = ?;",
                (idx, doc_id, project_id),
            )
    return {"status": "reordered", "count": len(payload.document_ids)}