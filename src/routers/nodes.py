from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.models import NodeModel
from src.services.hierarchy_service import (
    detach_selection_to_header,
    merge_nodes,
    promote_node_to_header,
    split_node,
)
from src.services.project_manager import get_project_connection

router = APIRouter(prefix="/api/projects/{project_id}/nodes", tags=["nodes"])

class SplitNodePayload(BaseModel):
    top_text: str
    bottom_text: str

class DetachSelectionPayload(BaseModel):
    selection_start: int
    selection_end: int

@router.get("", response_model=List[NodeModel])
async def get_project_nodes(project_id: str, document_id: Optional[str] = None):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    if document_id:
        cursor.execute(
            "SELECT * FROM nodes WHERE document_id = ? ORDER BY order_index ASC;",
            (document_id,),
        )
    else:
        cursor.execute(
            """
            SELECT n.* FROM nodes n
            JOIN documents d ON n.document_id = d.id
            WHERE d.project_id = ?
            ORDER BY d.order_index ASC, n.order_index ASC;
            """,
            (project_id,),
        )
    rows = cursor.fetchall()
    return [NodeModel(**dict(r)) for r in rows]

@router.post("/{node_id}/split", response_model=List[NodeModel])
async def api_split_node(project_id: str, node_id: str, payload: SplitNodePayload):
    conn = get_project_connection(project_id)
    try:
        upper, lower = split_node(conn, node_id, payload.top_text, payload.bottom_text)
        return [upper, lower]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{node_id}/merge", response_model=NodeModel)
async def api_merge_node(project_id: str, node_id: str):
    conn = get_project_connection(project_id)
    try:
        merged = merge_nodes(conn, node_id)
        return merged
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{node_id}/promote", response_model=NodeModel)
async def api_promote_node(project_id: str, node_id: str):
    conn = get_project_connection(project_id)
    try:
        promoted = promote_node_to_header(conn, node_id)
        return promoted
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{node_id}/detach-selection", response_model=List[NodeModel])
async def api_detach_selection(project_id: str, node_id: str, payload: DetachSelectionPayload):
    conn = get_project_connection(project_id)
    try:
        nodes = detach_selection_to_header(conn, node_id, payload.selection_start, payload.selection_end)
        return nodes
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))