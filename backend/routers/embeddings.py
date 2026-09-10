import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.services.embedding_service import (
    compile_contextual_payload,
    get_faiss_manager,
    handle_embedding_model_switch,
    run_partitioned_embeddings_refresh,
)
from backend.services.project_manager import get_project_connection

logger = logging.getLogger("custodex.embeddings_router")
router = APIRouter(prefix="/api/projects/{project_id}/embeddings", tags=["embeddings"])

class ModelSwitchCheckPayload(BaseModel):
    new_model: str
    confirm: bool = False

class StartEmbeddingPayload(BaseModel):
    batch_size: int = 16

@router.get("/status")
async def get_embedding_status(project_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN n.embedding_status = 'current' THEN 1 ELSE 0 END) as current_count,
            SUM(CASE WHEN n.embedding_status = 'stale' THEN 1 ELSE 0 END) as stale_count,
            SUM(CASE WHEN n.embedding_status = 'missing' THEN 1 ELSE 0 END) as missing_count,
            COUNT(n.id) as total_chunks
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.node_type = 'paragraph';
        """,
        (project_id,),
    )
    row = cursor.fetchone()
    mgr = get_faiss_manager(project_id)

    return {
        "project_id": project_id,
        "current": row["current_count"] or 0,
        "stale": row["stale_count"] or 0,
        "missing": row["missing_count"] or 0,
        "total": row["total_chunks"] or 0,
        "faiss_total": mgr.index.ntotal if mgr.index else 0,
    }

@router.post("/model-check")
async def check_and_update_model(project_id: str, payload: ModelSwitchCheckPayload):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT embedding_model FROM projects WHERE id = ?;", (project_id,))
    row = cursor.fetchone()
    current_model = row["embedding_model"] if row else ""

    if current_model == payload.new_model:
        return {"action": "unchanged", "requires_confirmation": False}

    cursor.execute(
        """
        SELECT COUNT(e.node_id) as count
        FROM node_embeddings e
        JOIN nodes n ON e.node_id = n.id
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.embedding_status = 'current';
        """,
        (project_id,),
    )
    existing_vectors = cursor.fetchone()["count"]

    if existing_vectors > 0 and not payload.confirm:
        return {
            "action": "requires_confirmation",
            "requires_confirmation": True,
            "existing_vectors": existing_vectors,
            "current_model": current_model,
            "new_model": payload.new_model,
            "message": f"Changing embedding model from '{current_model}' to '{payload.new_model}' will invalidate {existing_vectors} existing embeddings.",
        }

    res = handle_embedding_model_switch(conn, project_id, payload.new_model)
    return {"action": "switched", "requires_confirmation": False, "result": res}

@router.post("/refresh")
async def refresh_embeddings_sync(project_id: str, payload: StartEmbeddingPayload):
    conn = get_project_connection(project_id)
    try:
        result = run_partitioned_embeddings_refresh(
            conn=conn,
            project_id=project_id,
            batch_size=payload.batch_size,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream")
async def stream_embedding_generation(project_id: str, batch_size: int = Query(default=16)):
    conn = get_project_connection(project_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue()

        def on_part_start(p_idx: int, total_p: int, c_start: int, c_end: int):
            queue.put_nowait({
                "type": "progress",
                "data": {
                    "status": "running",
                    "completed_partitions": p_idx,
                    "total_partitions": total_p,
                    "chunk_start": c_start,
                    "chunk_end": c_end,
                }
            })

        def on_chunk_done(node_id: str, done_count: int, total_count: int):
            queue.put_nowait({
                "type": "progress",
                "data": {
                    "status": "running",
                    "completed_chunks": done_count,
                    "total_chunks": total_count,
                    "current_node_id": node_id,
                }
            })

        def on_part_done(p_idx: int, total_p: int):
            queue.put_nowait({
                "type": "progress",
                "data": {
                    "status": "running",
                    "completed_partitions": p_idx + 1,
                    "total_partitions": total_p,
                }
            })

        def worker():
            try:
                result = run_partitioned_embeddings_refresh(
                    conn=conn,
                    project_id=project_id,
                    batch_size=batch_size,
                    on_partition_start=on_part_start,
                    on_chunk_completed=on_chunk_done,
                    on_partition_completed=on_part_done,
                )
                queue.put_nowait({"type": "complete", "data": result})
            except Exception as exc:
                queue.put_nowait({"type": "failure", "data": {"error": str(exc)}})

        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, worker)

        while True:
            item = await queue.get()
            ev_type = item["type"]
            ev_data = json.dumps(item["data"])
            yield f"event: {ev_type}\ndata: {ev_data}\n\n"
            if ev_type in ("complete", "failure"):
                break

        await future

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )