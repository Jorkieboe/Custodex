import json
import sqlite3
from unittest.mock import MagicMock
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.main import app
from backend.services.embedding_service import (
    FaissIndexManager,
    blob_to_vector,
    compile_contextual_payload,
    handle_embedding_model_switch,
    run_partitioned_embeddings_refresh,
    vector_to_blob,
)
from backend.services.project_manager import register_custom_connection
from backend.services.semantic_splitter import (
    accept_semantic_split,
    calculate_candidate_split_points,
    preview_semantic_splits_for_nodes,
)

client = TestClient(app)

@pytest.fixture
def memory_project():
    project_id = "test_emb_proj"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'Emb Project', 'llm', 'test-emb');",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_1', ?, 'overview.md', 'md', 0);",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('h1', 'doc_1', NULL, 'header', 'System Architecture', 0, 'current');",
        )
        long_text = (
            "Sentence one discusses primary database ingestion. "
            "Sentence two elaborates on relational storage and persistence invariants. "
            "\n\nSentence three introduces vector retrieval and semantic indexing methods. "
            "Sentence four concludes retrieval evaluations and benchmarking results."
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c1', 'doc_1', 'h1', 'paragraph', ?, 1, 'missing');",
            (long_text,),
        )
        conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('c2', 'doc_1', 'h1', 'paragraph', 'Short trailing paragraph.', 2, 'current');",
        )

    register_custom_connection(project_id, conn)
    yield (project_id, conn)
    conn.close()

def test_semantic_split_candidate_preview_and_acceptance(memory_project):
    project_id, conn = memory_project

    previews = preview_semantic_splits_for_nodes(conn, ["c1"])
    assert len(previews) == 1
    p = previews[0]
    assert p["node_id"] == "c1"
    assert len(p["proposed_splits"]) >= 1

    first_split = p["proposed_splits"][0]
    cut_index = first_split["split_index"]
    assert cut_index > 0

    created = accept_semantic_split(conn, "c1", [cut_index])
    assert len(created) == 2
    assert created[0].id == "c1"
    assert created[0].order_index == 1
    assert created[0].embedding_status == "stale"

    assert created[1].id != "c1"
    assert created[1].order_index == 2
    assert created[1].embedding_status == "missing"

    cursor = conn.cursor()
    cursor.execute("SELECT id, order_index, embedding_status FROM nodes WHERE document_id = 'doc_1' ORDER BY order_index ASC;")
    rows = cursor.fetchall()
    assert len(rows) == 4
    assert [r["order_index"] for r in rows] == [0, 1, 2, 3]
    # c2 shifted to index 3
    assert rows[3]["id"] == "c2"

def test_contextual_payload_compiler(memory_project):
    project_id, conn = memory_project
    payload = compile_contextual_payload(conn, "c1")
    assert "overview.md" in payload
    assert "## System Architecture" in payload
    assert "Sentence one discusses" in payload

def test_faiss_vector_serialization_and_manager(memory_project):
    project_id, conn = memory_project
    v1 = [0.1, 0.2, 0.3, 0.4]
    b1 = vector_to_blob(v1)

    with conn:
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('c2', ?);",
            (b1,),
        )

    mgr = FaissIndexManager(project_id)
    count = mgr.sync_from_database(conn)
    assert count == 1
    assert mgr.node_id_map == ["c2"]

    serialized = mgr.serialize_faiss_bytes()
    assert serialized is not None
    assert len(serialized) > 0

def test_model_switch_invalidates_embeddings(memory_project):
    project_id, conn = memory_project
    with conn:
        conn.execute(
            "INSERT INTO node_embeddings (node_id, embedding_blob) VALUES ('c2', ?);",
            (vector_to_blob([1.0, 0.0]),),
        )

    check_resp = client.post(
        f"/api/projects/{project_id}/embeddings/model-check",
        json={"new_model": "new-embedding-model", "confirm": False},
    )
    assert check_resp.status_code == 200
    data = check_resp.json()
    assert data["action"] == "requires_confirmation"
    assert data["requires_confirmation"] is True

    # Now confirm switch
    switch_resp = client.post(
        f"/api/projects/{project_id}/embeddings/model-check",
        json={"new_model": "new-embedding-model", "confirm": True},
    )
    assert switch_resp.status_code == 200
    res_data = switch_resp.json()
    assert res_data["action"] == "switched"

    cursor = conn.cursor()
    cursor.execute("SELECT embedding_status FROM nodes WHERE id = 'c2';")
    assert cursor.fetchone()["embedding_status"] == "stale"

    cursor.execute("SELECT COUNT(*) as count FROM node_embeddings;")
    assert cursor.fetchone()["count"] == 0

def test_sentence_preserving_boundary_respect():
    sample_text = (
        "First sentence provides critical domain architecture. "
        "Second sentence adds technical details regarding ingestion pipelines. "
        "\n\nThird sentence introduces vector retrieval and embedding distances. "
        "Fourth sentence provides conclusion and verification results."
    )
    splits = calculate_candidate_split_points(sample_text, min_chunk_char_length=60, max_chunk_char_length=150)
    assert len(splits) >= 1
    for s in splits:
        cut = s["split_index"]
        char_before = sample_text[cut - 1]
        assert char_before in (".", "!", "?", "\n", " ")
        assert not sample_text[cut - 1].isalnum() or sample_text[cut] in (" ", "\n")

def test_token_budget_split_constraints():
    long_passage = (
        "Retrieval-Augmented Generation enhances generative AI models by fetching relevant context. "
        "Chunking strategy directly influences precision, recall, and downstream relevance. "
        "Small chunks preserve distinct factual units and pinpoint answers. "
        "Large chunks provide wider narrative context and surrounding discussion. "
        "Configuring token boundaries ensures vectors fit comfortably inside embedding context windows."
    )
    # Fine-grained token budget: 15 to 25 tokens
    fine_splits = calculate_candidate_split_points(long_passage, min_chunk_tokens=15, max_chunk_tokens=30)
    assert len(fine_splits) >= 1

    # Broad token budget: 100 to 200 tokens (entire passage is ~70 tokens, so no split)
    broad_splits = calculate_candidate_split_points(long_passage, min_chunk_tokens=100, max_chunk_tokens=200)
    assert len(broad_splits) == 0