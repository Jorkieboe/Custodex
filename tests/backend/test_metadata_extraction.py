import json
import sqlite3
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.main import app
from backend.services.metadata_extractor import (
    run_partitioned_metadata_extraction,
    get_existing_chunk_metadata,
)
from backend.services.project_manager import register_custom_connection

client = TestClient(app)

@pytest.fixture
def memory_project():
    project_id = "test_meta_proj"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'Metadata Project', 'mock-llm', 'mock-emb');",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_1', ?, 'doc1.md', 'md', 0);",
            (project_id,),
        )
        # Create 3 chunks
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c1', 'doc_1', NULL, 'paragraph', 'Content of chunk one.', 0, 'current');"
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c2', 'doc_1', NULL, 'paragraph', 'Content of chunk two.', 1, 'current');"
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c3', 'doc_1', NULL, 'paragraph', 'Content of chunk three.', 2, 'current');"
        )
        # Create schema fields
        conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index) VALUES ('f_topic', ?, 'topic', 'Topic', 'string', 'Main topic', 1, 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index) VALUES ('f_tags', ?, 'tags', 'Tags', 'array[string]', 'Tags list', 0, 1);",
            (project_id,),
        )

    register_custom_connection(project_id, conn)
    yield (project_id, conn)
    conn.close()

def test_partitioned_metadata_extraction_success(memory_project):
    project_id, conn = memory_project

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"topic": "AI Overview", "tags": ["rag", "ai"]})))
    ]
    mock_client.chat.completions.create.return_value = mock_resp

    result = run_partitioned_metadata_extraction(
        conn=conn,
        project_id=project_id,
        llm_client=mock_client,
        llm_model="mock-llm",
        batch_size=2,
    )

    assert result["status"] == "completed"
    assert result["total_chunks"] == 3
    assert result["total_partitions"] == 2

    # Verify committed values
    c1_meta = get_existing_chunk_metadata(conn, "c1")
    assert "f_topic" in c1_meta
    assert c1_meta["f_topic"]["value"] == "AI Overview"
    assert c1_meta["f_topic"]["user_edited"] is False

    # Verify checkpoints
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM batch_checkpoints WHERE job_type = 'metadata';")
    checkpoint = cursor.fetchone()
    assert checkpoint["completed_partition"] == 2
    assert checkpoint["status"] == "completed"

def test_user_edited_field_protection(memory_project):
    project_id, conn = memory_project

    # Human edited field
    with conn:
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('c1', 'f_topic', '\"Human Topic\"', 1);"
        )

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"topic": "AI Topic", "tags": ["tag1"]})))
    ]
    mock_client.chat.completions.create.return_value = mock_resp

    # Run without force_overwrite
    run_partitioned_metadata_extraction(
        conn=conn,
        project_id=project_id,
        llm_client=mock_client,
        llm_model="mock-llm",
        batch_size=3,
        force_overwrite=False,
    )

    c1_meta = get_existing_chunk_metadata(conn, "c1")
    assert c1_meta["f_topic"]["value"] == "Human Topic"
    assert c1_meta["f_topic"]["user_edited"] is True
    # Non-edited tags field should be updated
    assert c1_meta["f_tags"]["value"] == ["tag1"]
    assert c1_meta["f_tags"]["user_edited"] is False

    # Now run with force_overwrite = True
    run_partitioned_metadata_extraction(
        conn=conn,
        project_id=project_id,
        llm_client=mock_client,
        llm_model="mock-llm",
        batch_size=3,
        force_overwrite=True,
    )

    c1_meta_overwritten = get_existing_chunk_metadata(conn, "c1")
    assert c1_meta_overwritten["f_topic"]["value"] == "AI Topic"
    assert c1_meta_overwritten["f_topic"]["user_edited"] is False

def test_resumable_checkpoint_on_partition_failure(memory_project):
    project_id, conn = memory_project

    mock_client = MagicMock()
    calls = 0

    def side_effect(*args, **kwargs):
        nonlocal calls
        calls += 1
        # Part 1 succeeds (chunks 1 & 2), Part 2 fails (chunk 3)
        if calls > 2:
            raise RuntimeError("LM Studio connection timeout / OOM")
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content=json.dumps({"topic": "Part 1 Topic", "tags": []})))
        ]
        return mock_resp

    mock_client.chat.completions.create.side_effect = side_effect

    with pytest.raises(RuntimeError):
        run_partitioned_metadata_extraction(
            conn=conn,
            project_id=project_id,
            llm_client=mock_client,
            llm_model="mock-llm",
            batch_size=2,
            resume=False,
        )

    # Check that Part 1 remained committed in SQLite
    c1_meta = get_existing_chunk_metadata(conn, "c1")
    assert c1_meta["f_topic"]["value"] == "Part 1 Topic"

    cursor = conn.cursor()
    cursor.execute("SELECT completed_partition, status, last_error FROM batch_checkpoints WHERE job_type = 'metadata' ORDER BY id DESC LIMIT 1;")
    row = cursor.fetchone()
    assert row["completed_partition"] == 1
    assert row["status"] == "failed"
    assert "timeout / OOM" in row["last_error"]

    # Now fix error and resume
    mock_client.chat.completions.create.side_effect = None
    mock_resp_resume = MagicMock()
    mock_resp_resume.choices = [
        MagicMock(message=MagicMock(content=json.dumps({"topic": "Part 2 Resumed", "tags": ["resumed"]})))
    ]
    mock_client.chat.completions.create.return_value = mock_resp_resume

    resumed_result = run_partitioned_metadata_extraction(
        conn=conn,
        project_id=project_id,
        llm_client=mock_client,
        llm_model="mock-llm",
        batch_size=2,
        resume=True,
    )

    assert resumed_result["status"] == "completed"
    c3_meta = get_existing_chunk_metadata(conn, "c3")
    assert c3_meta["f_topic"]["value"] == "Part 2 Resumed"

def test_node_metadata_api_endpoints(memory_project):
    project_id, conn = memory_project

    # Get node metadata
    get_resp = client.get(f"/api/projects/{project_id}/nodes/c1/metadata")
    assert get_resp.status_code == 200
    items = get_resp.json()
    assert len(items) == 2

    # Put manual override
    put_resp = client.put(
        f"/api/projects/{project_id}/nodes/c1/metadata",
        json={"metadata": {"f_topic": "Manual Put Topic"}},
    )
    assert put_resp.status_code == 200

    # Verify user_edited is 1
    get_resp_updated = client.get(f"/api/projects/{project_id}/nodes/c1/metadata")
    topic_item = [i for i in get_resp_updated.json() if i["field_id"] == "f_topic"][0]
    assert topic_item["field_value"] == "Manual Put Topic"
    assert topic_item["user_edited"] is True