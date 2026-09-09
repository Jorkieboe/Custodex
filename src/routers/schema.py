import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.db.models import FieldType, SchemaFieldModel, generate_uuid, generate_json_schema_from_fields
from src.services.project_manager import get_project_connection, ensure_project_record

router = APIRouter(prefix="/api/projects/{project_id}/schema", tags=["schema"])

def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "_", cleaned)

class CreateFieldPayload(BaseModel):
    field_label: str
    field_slug: Optional[str] = None
    field_type: FieldType = "string"
    description: str = ""
    is_required: bool = False

class UpdateFieldPayload(BaseModel):
    field_label: Optional[str] = None
    field_slug: Optional[str] = None
    field_type: Optional[FieldType] = None
    description: Optional[str] = None
    is_required: Optional[bool] = None
    order_index: Optional[int] = None

@router.get("", response_model=List[SchemaFieldModel])
async def get_project_schema(project_id: str):
    conn = get_project_connection(project_id)
    ensure_project_record(conn, project_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC, id ASC;",
        (project_id,),
    )
    rows = cursor.fetchall()
    return [SchemaFieldModel(**dict(r)) for r in rows]

@router.get("/json-schema")
async def get_compiled_json_schema(project_id: str):
    conn = get_project_connection(project_id)
    ensure_project_record(conn, project_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;",
        (project_id,),
    )
    rows = cursor.fetchall()
    fields = [SchemaFieldModel(**dict(r)) for r in rows]
    return generate_json_schema_from_fields(fields)

@router.post("/fields", response_model=SchemaFieldModel)
async def create_schema_field(project_id: str, payload: CreateFieldPayload):
    conn = get_project_connection(project_id)
    ensure_project_record(conn, project_id)

    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(MAX(order_index), -1) as max_idx FROM schema_fields WHERE project_id = ?;",
        (project_id,),
    )
    next_order = cursor.fetchone()["max_idx"] + 1

    field_id = generate_uuid()
    slug = slugify(payload.field_slug or payload.field_label)
    if not slug:
        slug = f"field_{field_id[:8]}"

    field = SchemaFieldModel(
        id=field_id,
        project_id=project_id,
        field_slug=slug,
        field_label=payload.field_label.strip() or "Untitled Field",
        field_type=payload.field_type,
        description=payload.description.strip(),
        is_required=payload.is_required,
        order_index=next_order,
    )

    with conn:
        conn.execute(
            """
            INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                field.id,
                field.project_id,
                field.field_slug,
                field.field_label,
                field.field_type,
                field.description,
                int(field.is_required),
                field.order_index,
            ),
        )

    return field

@router.patch("/fields/{field_id}", response_model=SchemaFieldModel)
async def update_schema_field(project_id: str, field_id: str, payload: UpdateFieldPayload):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schema_fields WHERE id = ? AND project_id = ?;", (field_id, project_id))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Schema field not found")

    current = dict(row)
    new_label = payload.field_label if payload.field_label is not None else current["field_label"]
    new_slug = payload.field_slug if payload.field_slug is not None else current["field_slug"]
    new_slug = slugify(new_slug) or current["field_slug"]
    new_type = payload.field_type if payload.field_type is not None else current["field_type"]
    new_desc = payload.description if payload.description is not None else current["description"]
    new_req = payload.is_required if payload.is_required is not None else bool(current["is_required"])
    new_order = payload.order_index if payload.order_index is not None else current["order_index"]

    with conn:
        conn.execute(
            """
            UPDATE schema_fields
            SET field_label = ?, field_slug = ?, field_type = ?, description = ?, is_required = ?, order_index = ?
            WHERE id = ? AND project_id = ?;
            """,
            (new_label, new_slug, new_type, new_desc, int(new_req), new_order, field_id, project_id),
        )

    return SchemaFieldModel(
        id=field_id,
        project_id=project_id,
        field_slug=new_slug,
        field_label=new_label,
        field_type=new_type,
        description=new_desc,
        is_required=new_req,
        order_index=new_order,
    )

@router.delete("/fields/{field_id}")
async def delete_schema_field(project_id: str, field_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM schema_fields WHERE id = ? AND project_id = ?;", (field_id, project_id))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Schema field not found")

    with conn:
        conn.execute("DELETE FROM schema_fields WHERE id = ? AND project_id = ?;", (field_id, project_id))
        # Re-compact order_index
        cursor.execute(
            "SELECT id FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;",
            (project_id,),
        )
        remaining = cursor.fetchall()
        for idx, row in enumerate(remaining):
            conn.execute("UPDATE schema_fields SET order_index = ? WHERE id = ?;", (idx, row["id"]))

    return {"status": "deleted", "field_id": field_id}

@router.put("", response_model=List[SchemaFieldModel])
async def replace_all_schema_fields(project_id: str, fields: List[SchemaFieldModel]):
    conn = get_project_connection(project_id)
    ensure_project_record(conn, project_id)

    with conn:
        # Keep track of existing IDs
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM schema_fields WHERE project_id = ?;", (project_id,))
        existing_ids = {r["id"] for r in cursor.fetchall()}
        incoming_ids = {f.id for f in fields}

        # Delete removed fields
        to_delete = existing_ids - incoming_ids
        for del_id in to_delete:
            conn.execute("DELETE FROM schema_fields WHERE id = ? AND project_id = ?;", (del_id, project_id))

        # Upsert remaining fields with updated order_index
        for idx, f in enumerate(fields):
            slug = slugify(f.field_slug or f.field_label) or f"field_{f.id[:8]}"
            if f.id in existing_ids:
                conn.execute(
                    """
                    UPDATE schema_fields
                    SET field_slug = ?, field_label = ?, field_type = ?, description = ?, is_required = ?, order_index = ?
                    WHERE id = ? AND project_id = ?;
                    """,
                    (slug, f.field_label, f.field_type, f.description, int(f.is_required), idx, f.id, project_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (f.id, project_id, slug, f.field_label, f.field_type, f.description, int(f.is_required), idx),
                )

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;", (project_id,))
    rows = cursor.fetchall()
    return [SchemaFieldModel(**dict(r)) for r in rows]