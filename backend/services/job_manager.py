import asyncio
import json
import sqlite3
from typing import AsyncGenerator, Dict, Optional
from openai import OpenAI

try:
    from backend.services.metadata_extractor import run_partitioned_metadata_extraction
except ImportError:
    from src.services.metadata_extractor import run_partitioned_metadata_extraction

class JobState:
    def __init__(self, project_id: str, job_type: str = "metadata"):
        self.project_id = project_id
        self.job_type = job_type
        self.status: str = "idle"
        self.completed_partitions: int = 0
        self.total_partitions: int = 0
        self.completed_chunks: int = 0
        self.total_chunks: int = 0
        self.last_error: Optional[str] = None
        self.subscribers: list[asyncio.Queue] = []

    def broadcast(self, event_type: str, data: dict):
        payload = {"event": event_type, "data": data}
        for q in list(self.subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

_active_jobs: Dict[str, JobState] = {}

def get_or_create_job_state(project_id: str, job_type: str = "metadata") -> JobState:
    key = f"{project_id}_{job_type}"
    if key not in _active_jobs:
        _active_jobs[key] = JobState(project_id, job_type)
    return _active_jobs[key]

async def subscribe_job_events(project_id: str, job_type: str = "metadata") -> AsyncGenerator[str, None]:
    state = get_or_create_job_state(project_id, job_type)
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    state.subscribers.append(queue)

    initial_event = {
        "event": "state",
        "data": {
            "status": state.status,
            "completed_partitions": state.completed_partitions,
            "total_partitions": state.total_partitions,
            "completed_chunks": state.completed_chunks,
            "total_chunks": state.total_chunks,
            "last_error": state.last_error,
        },
    }
    yield f"data: {json.dumps(initial_event)}\n\n"

    try:
        while True:
            msg = await queue.get()
            yield f"data: {json.dumps(msg)}\n\n"
            if msg.get("event") in ("completed", "error"):
                break
    finally:
        if queue in state.subscribers:
            state.subscribers.remove(queue)

def execute_metadata_extraction_task(
    conn: sqlite3.Connection,
    project_id: str,
    llm_client: OpenAI,
    llm_model: str,
    batch_size: int = 10,
    force_overwrite: bool = False,
    resume: bool = False,
):
    state = get_or_create_job_state(project_id, "metadata")
    state.status = "running"
    state.last_error = None

    def on_part_start(p_idx: int, total_p: int, c_start: int, c_end: int):
        state.completed_partitions = p_idx
        state.total_partitions = total_p
        state.broadcast(
            "partition_start",
            {
                "partition_index": p_idx + 1,
                "total_partitions": total_p,
                "chunk_start": c_start,
                "chunk_end": c_end,
            },
        )

    def on_chunk_done(node_id: str, completed_c: int, total_c: int):
        state.completed_chunks = completed_c
        state.total_chunks = total_c
        state.broadcast(
            "chunk_progress",
            {
                "node_id": node_id,
                "completed_chunks": completed_c,
                "total_chunks": total_c,
            },
        )

    def on_part_done(p_idx: int, total_p: int):
        state.completed_partitions = p_idx + 1
        state.broadcast(
            "partition_complete",
            {
                "partition_index": p_idx + 1,
                "total_partitions": total_p,
            },
        )

    try:
        result = run_partitioned_metadata_extraction(
            conn=conn,
            project_id=project_id,
            llm_client=llm_client,
            llm_model=llm_model,
            batch_size=batch_size,
            force_overwrite=force_overwrite,
            resume=resume,
            on_partition_start=on_part_start,
            on_chunk_completed=on_chunk_done,
            on_partition_completed=on_part_done,
        )
        state.status = "completed"
        state.broadcast("completed", result)
    except Exception as e:
        state.status = "failed"
        state.last_error = str(e)
        state.broadcast(
            "error",
            {
                "error": str(e),
                "completed_partitions": state.completed_partitions,
                "total_partitions": state.total_partitions,
            },
        )