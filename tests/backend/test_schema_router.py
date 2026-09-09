import pytest
from fastapi.testclient import TestClient

from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.main import app
from backend.services.project_manager import register_custom_connection

client = TestClient(app)

@pytest.fixture
def test_project():
    project_id = "test_schema_project"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'Test Project', 'llm', 'emb');",
            (project_id,),
        )

    register_custom_connection(project_id, conn)
    yield project_id
    conn.close()

def test_schema_crud_and_json_schema_export(test_project):
    project_id = test_project

    # Create field
    create_resp = client.post(
        f"/api/projects/{project_id}/schema/fields",
        json={
            "field_slug": "summary",
            "field_label": "Summary",
            "field_type": "string",
            "description": "Short summary of the chunk",
            "is_required": True,
        },
    )
    assert create_resp.status_code == 200
    field = create_resp.json()
    assert field["field_slug"] == "summary"
    assert field["is_required"] is True
    field_id = field["id"]

    # Get schema list
    list_resp = client.get(f"/api/projects/{project_id}/schema")
    assert list_resp.status_code == 200
    fields = list_resp.json()
    assert len(fields) == 1
    assert fields[0]["id"] == field_id

    # Update field
    patch_resp = client.patch(
        f"/api/projects/{project_id}/schema/fields/{field_id}",
        json={"field_label": "Chunk Summary"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["field_label"] == "Chunk Summary"

    # Export compiled JSON Schema
    json_resp = client.get(f"/api/projects/{project_id}/schema/json")
    assert json_resp.status_code == 200
    schema_json = json_resp.json()
    assert "summary" in schema_json["properties"]
    assert schema_json["required"] == ["summary"]

    # Delete field
    del_resp = client.delete(f"/api/projects/{project_id}/schema/fields/{field_id}")
    assert del_resp.status_code == 200

    # Ensure list is now empty
    empty_resp = client.get(f"/api/projects/{project_id}/schema")
    assert empty_resp.status_code == 200
    assert len(empty_resp.json()) == 0