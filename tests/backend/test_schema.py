import pytest
from fastapi.testclient import TestClient

from src.db.connection import get_connection
from src.db.migrations import init_db
from src.main import app
from src.services.project_manager import register_custom_connection

client = TestClient(app)

@pytest.fixture
def memory_project():
    project_id = "test_schema_proj"
    conn = get_connection(":memory:")
    init_db(conn)

    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, llm_model, embedding_model) VALUES (?, 'Test Project', 'llm', 'emb');",
            (project_id,),
        )

    register_custom_connection(project_id, conn)
    yield (project_id, conn)
    conn.close()

def test_schema_field_crud_and_json_schema(memory_project):
    project_id, _ = memory_project

    # 1. Fetch initial empty schema
    resp = client.get(f"/api/projects/{project_id}/schema")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create string field
    resp = client.post(
        f"/api/projects/{project_id}/schema/fields",
        json={
            "field_label": "Summary Title",
            "field_slug": "summary_title",
            "field_type": "string",
            "description": "Short title of chunk",
            "is_required": True,
        },
    )
    assert resp.status_code == 200
    field1 = resp.json()
    assert field1["field_slug"] == "summary_title"
    assert field1["order_index"] == 0
    assert field1["is_required"] is True

    # 3. Create array[string] field with auto-slug
    resp = client.post(
        f"/api/projects/{project_id}/schema/fields",
        json={
            "field_label": "Key Concepts",
            "field_type": "array[string]",
            "description": "List of key terms",
            "is_required": False,
        },
    )
    assert resp.status_code == 200
    field2 = resp.json()
    assert field2["field_slug"] == "key_concepts"
    assert field2["order_index"] == 1

    # 4. Check JSON Schema endpoint
    json_schema_resp = client.get(f"/api/projects/{project_id}/schema/json-schema")
    assert json_schema_resp.status_code == 200
    js = json_schema_resp.json()
    assert js["type"] == "object"
    assert "summary_title" in js["properties"]
    assert "key_concepts" in js["properties"]
    assert js["properties"]["key_concepts"]["type"] == "array"
    assert js["required"] == ["summary_title"]

    # 5. Patch field
    patch_resp = client.patch(
        f"/api/projects/{project_id}/schema/fields/{field1['id']}",
        json={"field_label": "Updated Title", "description": "Modified prompt instruction"},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["field_label"] == "Updated Title"
    assert updated["description"] == "Modified prompt instruction"

    # 6. Delete field
    del_resp = client.delete(f"/api/projects/{project_id}/schema/fields/{field1['id']}")
    assert del_resp.status_code == 200

    # 7. Check remaining schema has recompacted order_index
    list_resp = client.get(f"/api/projects/{project_id}/schema")
    assert list_resp.status_code == 200
    remaining = list_resp.json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == field2["id"]
    assert remaining[0]["order_index"] == 0