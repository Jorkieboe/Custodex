import sqlite3
import pytest
from src.db.connection import get_connection
from src.db.migrations import init_db
from src.db.hierarchy import (
    format_contextual_breadcrumb_string,
    validate_acyclic_parent,
    densify_order_indices,
    shift_order_indices,
    cascade_header_stale_status,
)

@pytest.fixture
def db_conn():
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES ('proj_1', 'Test Project', 'llm', 'emb');"
        )
        conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES ('doc_1', 'proj_1', 'architecture.docx', 'docx', 0);"
        )

    yield conn
    conn.close()

def test_recursive_cte_hierarchy_breadcrumbs(db_conn):
    with db_conn:
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index) VALUES ('h1', 'doc_1', NULL, 'header', 'System Architecture', 0);"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index) VALUES ('h2', 'doc_1', 'h1', 'header', 'Data Flow', 1);"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index) VALUES ('c1', 'doc_1', 'h2', 'paragraph', 'Chunk text content.', 2);"
        )

    breadcrumb = format_contextual_breadcrumb_string(db_conn, "c1")
    expected = "architecture.docx > System Architecture > Data Flow > Chunk text content."
    assert breadcrumb == expected

def test_cycle_prevention_validator(db_conn):
    with db_conn:
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index) VALUES ('node_a', 'doc_1', NULL, 'header', 'A', 0);"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index) VALUES ('node_b', 'doc_1', 'node_a', 'header', 'B', 1);"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index) VALUES ('node_c', 'doc_1', 'node_b', 'paragraph', 'C', 2);"
        )

    assert validate_acyclic_parent(db_conn, "node_a", "node_a") is False
    assert validate_acyclic_parent(db_conn, "node_a", "node_c") is False
    assert validate_acyclic_parent(db_conn, "node_a", "node_b") is False
    assert validate_acyclic_parent(db_conn, "node_c", "node_a") is True
    assert validate_acyclic_parent(db_conn, "node_b", None) is True

def test_order_index_shifting_and_densification(db_conn):
    with db_conn:
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, node_type, text_content, order_index) VALUES ('n0', 'doc_1', 'paragraph', 'Zero', 0);"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, node_type, text_content, order_index) VALUES ('n1', 'doc_1', 'paragraph', 'One', 1);"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, node_type, text_content, order_index) VALUES ('n2', 'doc_1', 'paragraph', 'Two', 2);"
        )

    shift_order_indices(db_conn, "doc_1", start_index=1, delta=1)

    cursor = db_conn.cursor()
    cursor.execute("SELECT id, order_index FROM nodes WHERE document_id = 'doc_1' ORDER BY order_index ASC;")
    rows = cursor.fetchall()
    indices = {row["id"]: row["order_index"] for row in rows}

    assert indices["n0"] == 0
    assert indices["n1"] == 2
    assert indices["n2"] == 3

    with db_conn:
        db_conn.execute("DELETE FROM nodes WHERE id = 'n1';")

    densify_order_indices(db_conn, "doc_1")
    cursor.execute("SELECT id, order_index FROM nodes WHERE document_id = 'doc_1' ORDER BY order_index ASC;")
    densified_rows = cursor.fetchall()
    densified_indices = {row["id"]: row["order_index"] for row in densified_rows}

    assert densified_indices["n0"] == 0
    assert densified_indices["n2"] == 1

def test_cascade_header_stale_status(db_conn):
    with db_conn:
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('root_h', 'doc_1', NULL, 'header', 'Root Header', 0, 'current');"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('sub_h', 'doc_1', 'root_h', 'header', 'Sub Header', 1, 'current');"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('chunk_1', 'doc_1', 'sub_h', 'paragraph', 'Chunk 1', 2, 'current');"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('chunk_2', 'doc_1', 'root_h', 'paragraph', 'Chunk 2', 3, 'current');"
        )
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, parent_id, node_type, text_content, order_index, embedding_status) VALUES ('other_chunk', 'doc_1', NULL, 'paragraph', 'Independent Chunk', 4, 'current');"
        )

    affected = cascade_header_stale_status(db_conn, "sub_h")
    assert affected == 1

    cursor = db_conn.cursor()
    cursor.execute("SELECT id, embedding_status FROM nodes;")
    statuses = {row["id"]: row["embedding_status"] for row in cursor.fetchall()}

    assert statuses["chunk_1"] == "stale"
    assert statuses["chunk_2"] == "current"
    assert statuses["other_chunk"] == "current"

    affected_root = cascade_header_stale_status(db_conn, "root_h")
    assert affected_root == 2

    cursor.execute("SELECT id, embedding_status FROM nodes;")
    updated_statuses = {row["id"]: row["embedding_status"] for row in cursor.fetchall()}
    assert updated_statuses["sub_h"] == "stale"
    assert updated_statuses["chunk_2"] == "stale"