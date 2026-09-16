import io
import json
import sqlite3
import zipfile
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.main import app
from backend.services.embedding_service import vector_to_blob
from backend.services.export_service import build_rag_bundle, ValidationGateBlockedError
from backend.services.project_manager import register_custom_connection
from backend.services.validation_service import validate_project

client = TestClient(app)

@pytest.fixture
def memory_project():
    project_id = "test_export_proj"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'RAG Bundle Project', 'llm', 'emb');",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_1', ?, 'guide.md', 'md', 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index) VALUES ('f1', ?, 'topic', 'Topic', 'string', 'Primary topic', 1, 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('n1', 'doc_1', NULL, 'paragraph', 'Valid paragraph one text.', 0, 'current');",
        )
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('n1', ?);",
            (vector_to_blob([0.5, 0.5, 0.0]),),
        )
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('n1', 'f1', '\"Architecture\"', 0);",
        )

    register_custom_connection(project_id, conn)
    yield (project_id, conn)
    conn.close()

def test_validation_passes_when_all_concrete(memory_project):
    project_id, conn = memory_project
    res = validate_project(conn, project_id)
    assert res["is_valid"] is True
    assert res["total_blockers"] == 0
    assert len(res["blockers"]) == 0

def test_validation_blocks_on_empty_chunk(memory_project):
    project_id, conn = memory_project

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('n2', 'doc_1', NULL, 'paragraph', '   ', 1, 'current');",
        )
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('n2', ?);",
            (vector_to_blob([0.1, 0.2, 0.3]),),
        )
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('n2', 'f1', '\"Topic\"', 0);",
        )

    res = validate_project(conn, project_id)
    assert res["is_valid"] is False
    assert res["summary"]["empty_chunks"] == 1
    rules = [b["rule"] for b in res["blockers"]]
    assert "empty_chunk" in rules

def test_validation_blocks_on_stale_or_missing_embeddings(memory_project):
    project_id, conn = memory_project

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('n_stale', 'doc_1', NULL, 'paragraph', 'Content here', 1, 'stale');",
        )
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('n_stale', 'f1', '\"Topic\"', 0);",
        )

    res = validate_project(conn, project_id)
    assert res["is_valid"] is False
    assert res["summary"]["uncalculated_embeddings"] == 1

def test_validation_blocks_on_schema_violation_and_conflict(memory_project):
    project_id, conn = memory_project

    # Missing required field 'topic' on new chunk
    with conn:
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('n_req', 'doc_1', NULL, 'paragraph', 'Text content', 1, 'current');",
        )
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('n_req', ?);",
            (vector_to_blob([0.1, 0.2, 0.3]),),
        )

    res1 = validate_project(conn, project_id)
    assert res1["is_valid"] is False
    assert res1["summary"]["schema_violations"] == 1

    # Conflict marker present
    with conn:
        conflict_json = json.dumps({"has_conflict": True, "values": ["A", "B"]})
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('n_req', 'f1', ?, 0);",
            (conflict_json,),
        )

    res2 = validate_project(conn, project_id)
    assert res2["is_valid"] is False
    assert any("merge conflict" in b["message"] for b in res2["blockers"])

def test_build_rag_bundle_success_contents(memory_project):
    project_id, conn = memory_project

    zip_bytes, filename = build_rag_bundle(conn, project_id)
    assert filename == "rag_bundle_project-rag-bundle.zip"
    assert len(zip_bytes) > 0

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    assert set(names) == {"metadatascheme.json", "db.faiss", "dbmetadata.json"}

    # Validate dbmetadata.json
    dbmeta = json.loads(zf.read("dbmetadata.json").decode("utf-8"))
    assert len(dbmeta) == 1
    assert dbmeta[0]["chunk_id"] == "n1"
    assert dbmeta[0]["metadata"]["topic"] == "Architecture"
    assert "guide.md" in dbmeta[0]["breadcrumb"]

    # Validate metadatascheme.json
    scheme = json.loads(zf.read("metadatascheme.json").decode("utf-8"))
    assert "topic" in scheme["properties"]

    # Validate faiss non-empty
    faiss_data = zf.read("db.faiss")
    assert len(faiss_data) > 0

def test_build_rag_bundle_raises_on_blocker(memory_project):
    project_id, conn = memory_project

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('n_bad', 'doc_1', NULL, 'paragraph', 'Text', 1, 'missing');",
        )

    with pytest.raises(ValidationGateBlockedError):
        build_rag_bundle(conn, project_id)

def test_export_api_endpoints(memory_project):
    project_id, _ = memory_project

    # Test GET /validate
    val_resp = client.get(f"/api/projects/{project_id}/validate")
    assert val_resp.status_code == 200
    assert val_resp.json()["is_valid"] is True

    # Test GET /export
    export_resp = client.get(f"/api/projects/{project_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/zip"
    assert "attachment" in export_resp.headers["content-disposition"]