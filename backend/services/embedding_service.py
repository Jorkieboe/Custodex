import io
import json
import logging
import os
import sqlite3
import struct
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import faiss
import numpy as np
import openai

from backend.config import create_openai_client, get_embedding_endpoint, get_openai_api_key, load_config
from backend.db.hierarchy import get_node_ancestor_rows
from backend.db.models import NodeModel

logger = logging.getLogger("custodex.embeddings")

def compile_contextual_payload(conn: sqlite3.Connection, node_id: str) -> str:
    doc_filename, rows = get_node_ancestor_rows(conn, node_id)
    if not rows:
        return ""

    headers = []
    chunk_text = ""

    for r in rows:
        if r["node_type"] == "header":
            headers.append(r["text_content"])
        elif r["node_type"] == "paragraph":
            chunk_text = r["text_content"]

    payload_lines = [doc_filename]
    if headers:
        for idx, h in enumerate(headers, start=2):
            prefix = "#" * min(idx, 6)
            payload_lines.append(f"{prefix} {h}")
    payload_lines.append("")
    payload_lines.append(chunk_text)

    return "\n\n".join(line for line in payload_lines if line)

def vector_to_blob(vec: List[float]) -> bytes:
    arr = np.array(vec, dtype=np.float32)
    return arr.tobytes()

def blob_to_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)

class FaissIndexManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.index: Optional[faiss.IndexFlatIP] = None
        self.node_id_map: List[str] = []

    def sync_from_database(self, conn: sqlite3.Connection) -> int:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT n.id, e.embedding_blob
            FROM nodes n
            JOIN documents d ON n.document_id = d.id
            JOIN node_embeddings e ON n.id = e.node_id
            WHERE d.project_id = ? AND n.node_type = 'paragraph' AND n.embedding_status = 'current'
            ORDER BY d.order_index ASC, n.order_index ASC;
            """,
            (self.project_id,),
        )
        rows = cursor.fetchall()
        if not rows:
            self.index = None
            self.node_id_map = []
            return 0

        vectors = []
        ids = []
        for r in rows:
            v = blob_to_vector(r["embedding_blob"])
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            vectors.append(v)
            ids.append(r["id"])

        mat = np.vstack(vectors).astype(np.float32)
        dim = mat.shape[1]

        idx = faiss.IndexFlatIP(dim)
        idx.add(mat)
        self.index = idx
        self.node_id_map = ids
        return idx.ntotal

    def serialize_faiss_bytes(self) -> Optional[bytes]:
        if self.index is None:
            return None
        buf = faiss.serialize_index(self.index)
        return bytes(buf)

_index_cache: Dict[str, FaissIndexManager] = {}

def get_faiss_manager(project_id: str) -> FaissIndexManager:
    if project_id not in _index_cache:
        _index_cache[project_id] = FaissIndexManager(project_id)
    return _index_cache[project_id]

def get_embedding_client_for_model(model_name: str) -> Tuple[openai.OpenAI, str, str]:
    config = load_config()
    api_key = get_openai_api_key(config)
    endpoint = get_embedding_endpoint(config)

    is_openai = (
        model_name.lower().startswith("text-embedding")
        or "api.openai.com" in endpoint.lower()
    )

    if is_openai and not endpoint.strip():
        endpoint = "https://api.openai.com/v1"

    client = create_openai_client(endpoint, api_key=api_key, is_openai=is_openai)
    return client, model_name, endpoint

def run_partitioned_embeddings_refresh(
    conn: sqlite3.Connection,
    project_id: str,
    batch_size: int = 16,
    on_partition_start: Optional[Callable[[int, int, int, int], None]] = None,
    on_chunk_completed: Optional[Callable[[str, int, int], None]] = None,
    on_partition_completed: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT embedding_model FROM projects WHERE id = ?;", (project_id,))
    proj_row = cursor.fetchone()
    model_name = proj_row["embedding_model"] if proj_row else "text-embedding-multilingual-e5-base"

    cursor.execute(
        """
        SELECT n.id, n.document_id, n.text_content, n.order_index
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.node_type = 'paragraph' AND n.embedding_status != 'current'
        ORDER BY d.order_index ASC, n.order_index ASC;
        """,
        (project_id,),
    )
    targets = cursor.fetchall()
    total_targets = len(targets)

    print(f"target: {total_targets}")

    if total_targets == 0:
        mgr = get_faiss_manager(project_id)
        mgr.sync_from_database(conn)
        return {
            "status": "up_to_date",
            "total_chunks": 0,
            "total_partitions": 0,
            "processed_chunks": 0,
        }

    total_partitions = (total_targets + batch_size - 1) // batch_size
    client, active_model, endpoint = get_embedding_client_for_model(model_name)

    print(active_model)

    with conn:
        conn.execute(
            """
            INSERT INTO batch_checkpoints (job_type, completed_partition, total_partitions, status, last_error, updated_at)
            VALUES ('embedding', 0, ?, 'in_progress', NULL, CURRENT_TIMESTAMP);
            """,
            (total_partitions,),
        )

    processed_count = 0

    for p_idx in range(total_partitions):
        print(f"do: {p_idx}")
        chunk_start = p_idx * batch_size
        chunk_end = min(chunk_start + batch_size, total_targets)
        part_nodes = targets[chunk_start:chunk_end]

        if on_partition_start:
            on_partition_start(p_idx, total_partitions, chunk_start, chunk_end)

        payloads = []
        for row in part_nodes:
            ctx_payload = compile_contextual_payload(conn, row["id"])
            payloads.append(ctx_payload)
        print(client)

        try:
            resp = client.embeddings.create(
                model=active_model,
                input=payloads,
            )
            print(resp)
            vectors = [item.embedding for item in resp.data]

            print(vectors)

            with conn:
                for i, row in enumerate(part_nodes):
                    node_id = row["id"]
                    vec = vectors[i]
                    blob = vector_to_blob(vec)

                    conn.execute(
                        """
                        INSERT INTO node_embeddings (node_id, embedding_blob, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(node_id) DO UPDATE SET
                            embedding_blob = excluded.embedding_blob,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (node_id, blob),
                    )

                    conn.execute(
                        "UPDATE nodes SET embedding_status = 'current' WHERE id = ?;",
                        (node_id,),
                    )

                    processed_count += 1
                    if on_chunk_completed:
                        on_chunk_completed(node_id, processed_count, total_targets)

                conn.execute(
                    """
                    UPDATE batch_checkpoints
                    SET completed_partition = ?, status = 'in_progress', updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT MAX(id) FROM batch_checkpoints WHERE job_type = 'embedding');
                    """,
                    (p_idx + 1,),
                )

            if on_partition_completed:
                on_partition_completed(p_idx, total_partitions)

        except Exception as err:
            with conn:
                conn.execute(
                    """
                    UPDATE batch_checkpoints
                    SET status = 'failed', last_error = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT MAX(id) FROM batch_checkpoints WHERE job_type = 'embedding');
                    """,
                    (str(err),),
                )
            raise

    with conn:
        conn.execute(
            """
            UPDATE batch_checkpoints
            SET completed_partition = ?, status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = (SELECT MAX(id) FROM batch_checkpoints WHERE job_type = 'embedding');
            """,
            (total_partitions,),
        )

    mgr = get_faiss_manager(project_id)
    mgr.sync_from_database(conn)

    print("return chunks")

    return {
        "status": "completed",
        "total_chunks": total_targets,
        "total_partitions": total_partitions,
        "processed_chunks": processed_count,
    }

def handle_embedding_model_switch(conn: sqlite3.Connection, project_id: str, new_model: str) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(e.node_id) as valid_count
        FROM node_embeddings e
        JOIN nodes n ON e.node_id = n.id
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.embedding_status = 'current';
        """,
        (project_id,),
    )
    valid_count = cursor.fetchone()["valid_count"]

    with conn:
        conn.execute("UPDATE projects SET embedding_model = ? WHERE id = ?;", (new_model, project_id))
        conn.execute(
            """
            UPDATE nodes
            SET embedding_status = 'stale'
            WHERE document_id IN (SELECT id FROM documents WHERE project_id = ?)
              AND node_type = 'paragraph';
            """,
            (project_id,),
        )
        conn.execute(
            """
            DELETE FROM node_embeddings
            WHERE node_id IN (
                SELECT n.id FROM nodes n
                JOIN documents d ON n.document_id = d.id
                WHERE d.project_id = ?
            );
            """,
            (project_id,),
        )

    mgr = get_faiss_manager(project_id)
    mgr.index = None
    mgr.node_id_map = []

    return {
        "status": "model_updated",
        "invalidated_embeddings": valid_count,
        "new_model": new_model,
    }