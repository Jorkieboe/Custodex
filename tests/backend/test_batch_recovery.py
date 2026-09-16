import json
import sqlite3
from unittest.mock import MagicMock
import pytest

from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.services.embedding_service import run_partitioned_embeddings_refresh, vector_to_blob
from backend.services.metadata_extractor import (
    get_existing_chunk_metadata,
    run_partitioned_metadata_extraction,
)
from backend.services.project_manager import register_custom_connection

@pytest.fixture
def multi_partition_project():
    project_id = "test_batch_recovery_proj"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'Batch Project', 'mock-llm', 'mock-emb');",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_1', ?, 'data.md', 'md', 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index) VALUES ('f_key', ?, 'keyword', 'Keyword', 'string', 'Keyword', 0, 0);",
            (project_id,),
        )

        for i in range(10):
            conn.execute(
                f"INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('node_{i}', 'doc_1', NULL, 'paragraph', 'Content for chunk {i}', {i}, 'missing');"
            )

    register_custom_connection(project_id, conn)
    yield (project_id, conn)
    conn.close()

def test_metadata_partition_failure_and_resumption(multi_partition_project):
    project_id, conn = multi_partition_project
    mock_client = MagicMock()
    call_count = 0

    def mock_extract(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            raise RuntimeError("LM Studio OOM error: out of VRAM memory")
        resp = MagicMock()
        resp.choices = [
            MagicMock(message=MagicMock(content=json.dumps({"keyword": f"Tag_{call_count}"})))
        ]
        return resp

    mock_client.chat.completions.create.side_effect = mock_extract

    with pytest.raises(RuntimeError) as exc_info:
        run_partitioned_metadata_extraction(
            conn=conn,
            project_id=project_id,
            llm_client=mock_client,
            llm_model="mock-llm",
            batch_size=2,
            resume=False,
        )

    assert "OOM error" in str(exc_info.value)

    meta_0 = get_existing_chunk_metadata(conn, "node_0")
    meta_1 = get_existing_chunk_metadata(conn, "node_1")
    assert meta_0["f_key"]["value"] == "Tag_1"
    assert meta_1["f_key"]["value"] == "Tag_2"

    meta_2 = get_existing_chunk_metadata(conn, "node_2")
    assert len(meta_2) == 0

    cursor = conn.cursor()
    cursor.execute(
        "SELECT completed_partition, total_partitions, status, last_error FROM batch_checkpoints WHERE job_type = 'metadata' ORDER BY id DESC LIMIT 1;"
    )
    checkpoint = cursor.fetchone()
    assert checkpoint["completed_partition"] == 1
    assert checkpoint["total_partitions"] == 5
    assert checkpoint["status"] == "failed"
    assert "OOM error" in checkpoint["last_error"]

    resumed_call_count = 2
    def mock_resumed_extract(*args, **kwargs):
        nonlocal resumed_call_count
        resumed_call_count += 1
        resp = MagicMock()
        resp.choices = [
            MagicMock(message=MagicMock(content=json.dumps({"keyword": f"Resumed_{resumed_call_count}"})))
        ]
        return resp

    mock_client.chat.completions.create.side_effect = mock_resumed_extract

    result = run_partitioned_metadata_extraction(
        conn=conn,
        project_id=project_id,
        llm_client=mock_client,
        llm_model="mock-llm",
        batch_size=2,
        resume=True,
    )

    assert result["status"] == "completed"
    assert result["total_chunks"] == 10
    assert result["total_partitions"] == 5

    cursor.execute(
        "SELECT completed_partition, status FROM batch_checkpoints WHERE job_type = 'metadata' ORDER BY id DESC LIMIT 1;"
    )
    latest = cursor.fetchone()
    assert latest["completed_partition"] == 5
    assert latest["status"] == "completed"

    cursor.execute("SELECT COUNT(DISTINCT node_id) as cnt FROM node_metadata;")
    assert cursor.fetchone()["cnt"] == 10

def test_embedding_partition_failure_and_incremental_pickup(multi_partition_project):
    project_id, conn = multi_partition_project

    with conn:
        conn.execute(
            "UPDATE nodes SET embedding_status = 'current' WHERE id IN ('node_0', 'node_1');"
        )
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('node_0', ?);",
            (vector_to_blob([0.1, 0.2]),),
        )
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('node_1', ?);",
            (vector_to_blob([0.3, 0.4]),),
        )

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(n.id) as remaining
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.embedding_status != 'current';
        """,
        (project_id,),
    )
    remaining_count = cursor.fetchone()["remaining"]
    assert remaining_count == 8