from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.models import NodeModel
from backend.services.hierarchy_service import (
    change_node_type,
    demote_header_to_node,
    detach_selection_to_header,
    merge_nodes,
    promote_node_to_header,
    split_node,
    update_node_text,
)
from backend.services.project_manager import get_project_connection
from backend.services.semantic_splitter import (
    accept_semantic_split,
    preview_semantic_splits_for_nodes,
)

router = APIRouter(prefix="/api/projects/{project_id}/nodes", tags=["nodes"])

class SemanticSplitPreviewPayload(BaseModel):
    node_ids: List[str]
    min_tokens: Optional[int] = None
    max_tokens: Optional[int] = None

class BoundaryAcceptanceItem(BaseModel):
    node_id: str
    split_indices: List[int]

class SemanticSplitAcceptPayload(BaseModel):
    items: List[BoundaryAcceptanceItem]

class UpdateNodePayload(BaseModel):
    text_content: str

class SplitNodePayload(BaseModel):
    top_text: str
    bottom_text: str

class DetachSelectionPayload(BaseModel):
    selection_start: int
    selection_end: int

@router.get("", response_model=List[NodeModel])
async def get_project_nodes(project_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
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

@router.post("/semantic-split-preview")
async def preview_semantic_split(project_id: str, payload: SemanticSplitPreviewPayload):
    conn = get_project_connection(project_id)
    proposals = preview_semantic_splits_for_nodes(
        conn=conn,
        node_ids=payload.node_ids,
        min_tokens=payload.min_tokens,
        max_tokens=payload.max_tokens,
    )
    return proposals

@router.post("/semantic-split-accept")
async def accept_semantic_split_boundaries(project_id: str, payload: SemanticSplitAcceptPayload):
    conn = get_project_connection(project_id)
    all_affected_nodes: List[NodeModel] = []
    for item in payload.items:
        try:
            nodes = accept_semantic_split(conn, item.node_id, item.split_indices)
            all_affected_nodes.extend(nodes)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))
    return all_affected_nodes

@router.patch("/{node_id}", response_model=NodeModel)
async def api_update_node(project_id: str, node_id: str, payload: UpdateNodePayload):
    conn = get_project_connection(project_id)
    try:
        updated = update_node_text(conn, node_id, payload.text_content)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        promoted = change_node_type(conn, node_id, promote=True)
        return promoted
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{node_id}/demote", response_model=NodeModel)
async def api_demote_node(project_id: str, node_id: str):
    conn = get_project_connection(project_id)
    try:
        demoted = change_node_type(conn, node_id, promote=False)
        return demoted
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