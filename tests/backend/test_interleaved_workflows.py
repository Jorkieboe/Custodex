import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.db.models import DocumentModel, NodeModel, SchemaFieldModel
from backend.main import app
from backend.services.embedding_service import vector_to_blob
from backend.services.hierarchy_service import (
    change_node_type,
    demote_header_to_node,
    merge_nodes,
    promote_node_to_header,
    split_node,
    update_node_text,
)
from backend.services.metadata_extractor import get_existing_chunk_metadata
from backend.services.project_manager import register_custom_connection

client = TestClient(app)

@pytest.fixture
def memory_project():
    project_id = "test_interleaved_proj"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'Interleaved Test', 'llm', 'emb');",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_1', ?, 'doc1.md', 'md', 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index) VALUES ('f_topic', ?, 'topic', 'Topic', 'string', 'Main topic', 1, 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index) VALUES ('f_tags', ?, 'tags', 'Tags', 'array[string]', 'Tags list', 0, 1);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('h1', 'doc_1', NULL, 'header', 'Section 1', 0, 'current');",
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c1', 'doc_1', 'h1', 'paragraph', 'Upper paragraph text. Lower paragraph text.', 1, 'current');",
        )
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('c1', ?);",
            (vector_to_blob([0.1, 0.2, 0.3]),),
        )
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('c1', 'f_topic', '\"Original Topic\"', 1);",
        )
        conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES ('c1', 'f_tags', '[\"rag\", \"custodex\"]', 0);",
        )

    register_custom_connection(project_id, conn)
    yield (project_id, conn)
    conn.close()

def test_chunk_split_clears_metadata_on_both_slices(memory_project):
    project_id, conn = memory_project

    upper, lower = split_node(conn, "c1", "Upper paragraph text.", "Lower paragraph text.")

    assert upper.id == "c1"
    assert upper.order_index == 1
    assert upper.embedding_status == "stale"

    assert lower.id != "c1"
    assert lower.order_index == 2
    assert lower.embedding_status == "missing"

    meta_upper = get_existing_chunk_metadata(conn, "c1")
    assert len(meta_upper) == 0

    meta_lower = get_existing_chunk_metadata(conn, lower.id)
    assert len(meta_lower) == 0

def test_adding_new_document_preserves_existing_embeddings_and_metadata(memory_project):
    project_id, conn = memory_project

    with conn:
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_2', ?, 'doc2.txt', 'txt', 1);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c_new', 'doc_2', NULL, 'paragraph', 'New document content', 0, 'missing');",
        )

    cursor = conn.cursor()
    cursor.execute("SELECT embedding_status FROM nodes WHERE id = 'c1';")
    assert cursor.fetchone()["embedding_status"] == "current"

    cursor.execute("SELECT COUNT(*) as cnt FROM node_embeddings WHERE node_id = 'c1';")
    assert cursor.fetchone()["cnt"] == 1

    meta_existing = get_existing_chunk_metadata(conn, "c1")
    assert meta_existing["f_topic"]["value"] == "Original Topic"

    cursor.execute("SELECT COUNT(*) as doc_cnt FROM documents WHERE project_id = ?;", (project_id,))
    assert cursor.fetchone()["doc_cnt"] == 2

def test_header_mutation_cascades_stale_to_descendants_without_touching_metadata(memory_project):
    project_id, conn = memory_project

    update_node_text(conn, "h1", "Section 1: Modified Title")

    cursor = conn.cursor()
    cursor.execute("SELECT embedding_status FROM nodes WHERE id = 'c1';")
    assert cursor.fetchone()["embedding_status"] == "stale"

    meta = get_existing_chunk_metadata(conn, "c1")
    assert meta["f_topic"]["value"] == "Original Topic"
    assert meta["f_topic"]["user_edited"] is True

def test_schema_field_rename_and_reorder_preserves_node_metadata_associations(memory_project):
    project_id, conn = memory_project

    with conn:
        conn.execute(
            "UPDATE schema_fields SET field_slug = 'primary_subject', field_label = 'Primary Subject', order_index = 5 WHERE id = 'f_topic';"
        )

    resp = client.get(f"/api/projects/{project_id}/nodes/c1/metadata")
    assert resp.status_code == 200
    items = resp.json()

    subject_item = [i for i in items if i["field_id"] == "f_topic"][0]
    assert subject_item["field_slug"] == "primary_subject"
    assert subject_item["field_label"] == "Primary Subject"
    assert subject_item["field_value"] == "Original Topic"
    assert subject_item["user_edited"] is True