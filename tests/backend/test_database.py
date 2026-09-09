import sqlite3
import pytest
from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.db.models import (
    ProjectModel,
    DocumentModel,
    NodeModel,
    SchemaFieldModel,
    NodeMetadataModel,
    generate_json_schema_from_fields,
)

@pytest.fixture
def db_conn():
    conn = get_connection(":memory:")
    init_db(conn)
    yield conn
    conn.close()

def test_database_initialization(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row["name"] for row in cursor.fetchall()}
    expected_tables = {
        "projects",
        "documents",
        "nodes",
        "node_embeddings",
        "schema_fields",
        "node_metadata",
        "batch_checkpoints",
    }
    assert expected_tables.issubset(tables)

def test_foreign_key_cascades(db_conn):
    project = ProjectModel(name="Test Project", llm_model="test-llm", embedding_model="test-embed")
    with db_conn:
        db_conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, ?, ?, ?);",
            (project.id, project.name, project.llm_model, project.embedding_model),
        )

    doc = DocumentModel(project_id=project.id, filename="test.docx", file_type="docx", order_index=0)
    with db_conn:
        db_conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES (?, ?, ?, ?, ?);",
            (doc.id, doc.project_id, doc.filename, doc.file_type, doc.order_index),
        )

    node = NodeModel(
        document_id=doc.id,
        node_type="paragraph",
        text_content="Sample chunk content.",
        order_index=0,
    )
    with db_conn:
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, node_type, text_content, order_index, embedding_status) VALUES (?, ?, ?, ?, ?, ?);",
            (node.id, node.document_id, node.node_type, node.text_content, node.order_index, node.embedding_status),
        )

    with db_conn:
        db_conn.execute("DELETE FROM projects WHERE id = ?;", (project.id,))

    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM documents WHERE id = ?;", (doc.id,))
    assert cursor.fetchone()["count"] == 0
    cursor.execute("SELECT COUNT(*) as count FROM nodes WHERE id = ?;", (node.id,))
    assert cursor.fetchone()["count"] == 0

def test_schema_field_rename_preserves_chunk_metadata(db_conn):
    project = ProjectModel(name="Project", llm_model="m", embedding_model="e")
    with db_conn:
        db_conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, ?, ?, ?);",
            (project.id, project.name, project.llm_model, project.embedding_model),
        )

    doc = DocumentModel(project_id=project.id, filename="test.txt", file_type="txt", order_index=0)
    with db_conn:
        db_conn.execute(
            "INSERT INTO documents (id, project_id, filename, file_type, order_index) VALUES (?, ?, ?, ?, ?);",
            (doc.id, doc.project_id, doc.filename, doc.file_type, doc.order_index),
        )

    node = NodeModel(document_id=doc.id, node_type="paragraph", text_content="Chunk 1", order_index=0)
    with db_conn:
        db_conn.execute(
            "INSERT INTO nodes (id, document_id, node_type, text_content, order_index) VALUES (?, ?, ?, ?, ?);",
            (node.id, node.document_id, node.node_type, node.text_content, node.order_index),
        )

    field = SchemaFieldModel(
        project_id=project.id,
        field_slug="topic",
        field_label="Topic",
        field_type="string",
        order_index=0,
    )
    with db_conn:
        db_conn.execute(
            "INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, order_index) VALUES (?, ?, ?, ?, ?, ?);",
            (field.id, field.project_id, field.field_slug, field.field_label, field.field_type, field.order_index),
        )

    meta = NodeMetadataModel(node_id=node.id, field_id=field.id, field_value='"AI Engineering"')
    with db_conn:
        db_conn.execute(
            "INSERT INTO node_metadata (node_id, field_id, field_value, user_edited) VALUES (?, ?, ?, ?);",
            (meta.node_id, meta.field_id, meta.field_value, int(meta.user_edited)),
        )

    with db_conn:
        db_conn.execute(
            "UPDATE schema_fields SET field_slug = 'subject_area', field_label = 'Subject Area' WHERE id = ?;",
            (field.id,),
        )

    cursor = db_conn.cursor()
    cursor.execute("SELECT field_value FROM node_metadata WHERE node_id = ? AND field_id = ?;", (node.id, field.id))
    row = cursor.fetchone()
    assert row is not None
    assert row["field_value"] == '"AI Engineering"'

def test_json_schema_generation():
    fields = [
        SchemaFieldModel(
            project_id="p1",
            field_slug="title",
            field_label="Title",
            field_type="string",
            description="Extract concise title",
            is_required=True,
            order_index=0,
        ),
        SchemaFieldModel(
            project_id="p1",
            field_slug="confidence",
            field_label="Confidence",
            field_type="number",
            is_required=False,
            order_index=1,
        ),
        SchemaFieldModel(
            project_id="p1",
            field_slug="tags",
            field_label="Tags",
            field_type="array[string]",
            is_required=True,
            order_index=2,
        ),
    ]

    schema = generate_json_schema_from_fields(fields)
    assert schema["type"] == "object"
    assert "title" in schema["properties"]
    assert schema["properties"]["title"]["type"] == "string"
    assert schema["properties"]["title"]["description"] == "Extract concise title"
    assert schema["properties"]["tags"]["type"] == "array"
    assert schema["properties"]["tags"]["items"] == {"type": "string"}
    assert schema["required"] == ["title", "tags"]
    assert schema["additionalProperties"] is False