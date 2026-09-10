import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.models import (
    FieldType,
    SchemaFieldModel,
    generate_json_schema_from_fields,
    generate_uuid,
)
from backend.services.project_manager import get_project_connection

router = APIRouter(prefix="/api/projects/{project_id}/schema", tags=["schema"])

def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return slug.strip("_")

class CreateSchemaFieldPayload(BaseModel):
    field_slug: Optional[str] = None
    field_label: str
    field_type: FieldType = "string"
    description: str = ""
    is_required: bool = False
    order_index: Optional[int] = None

class UpdateSchemaFieldPayload(BaseModel):
    field_slug: Optional[str] = None
    field_label: Optional[str] = None
    field_type: Optional[FieldType] = None
    description: Optional[str] = None
    is_required: Optional[bool] = None
    order_index: Optional[int] = None

@router.get("", response_model=List[SchemaFieldModel])
async def get_project_schema(project_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;",
        (project_id,),
    )
    rows = cursor.fetchall()
    return [
        SchemaFieldModel(
            id=r["id"],
            project_id=r["project_id"],
            field_slug=r["field_slug"],
            field_label=r["field_label"],
            field_type=r["field_type"],
            description=r["description"],
            is_required=bool(r["is_required"]),
            order_index=r["order_index"],
        )
        for r in rows
    ]

@router.get("/json-schema")
async def get_compiled_json_schema(project_id: str):
    fields = await get_project_schema(project_id)
    return generate_json_schema_from_fields(fields)

@router.post("/fields", response_model=SchemaFieldModel)
async def create_schema_field(project_id: str, payload: CreateSchemaFieldPayload):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()

    order_idx = payload.order_index
    if order_idx is None:
        cursor.execute(
            "SELECT COALESCE(MAX(order_index), -1) as max_order FROM schema_fields WHERE project_id = ?;",
            (project_id,),
        )
        order_idx = cursor.fetchone()["max_order"] + 1

    slug = slugify(payload.field_slug) if payload.field_slug and payload.field_slug.strip() else slugify(payload.field_label)
    if not slug:
        slug = f"field_{order_idx}"

    field_id = generate_uuid()
    with conn:
        conn.execute(
            """
            INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                field_id,
                project_id,
                slug,
                payload.field_label,
                payload.field_type,
                payload.description,
                int(payload.is_required),
                order_idx,
            ),
        )

    return SchemaFieldModel(
        id=field_id,
        project_id=project_id,
        field_slug=slug,
        field_label=payload.field_label,
        field_type=payload.field_type,
        description=payload.description,
        is_required=payload.is_required,
        order_index=order_idx,
    )

@router.patch("/fields/{field_id}", response_model=SchemaFieldModel)
async def update_schema_field(project_id: str, field_id: str, payload: UpdateSchemaFieldPayload):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schema_fields WHERE id = ? AND project_id = ?;", (field_id, project_id))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Schema field not found")

    new_slug = payload.field_slug if payload.field_slug is not None else row["field_slug"]
    new_label = payload.field_label if payload.field_label is not None else row["field_label"]
    new_type = payload.field_type if payload.field_type is not None else row["field_type"]
    new_desc = payload.description if payload.description is not None else row["description"]
    new_required = payload.is_required if payload.is_required is not None else bool(row["is_required"])
    new_order = payload.order_index if payload.order_index is not None else row["order_index"]

    with conn:
        conn.execute(
            """
            UPDATE schema_fields
            SET field_slug = ?, field_label = ?, field_type = ?, description = ?, is_required = ?, order_index = ?
            WHERE id = ? AND project_id = ?;
            """,
            (new_slug, new_label, new_type, new_desc, int(new_required), new_order, field_id, project_id),
        )

    return SchemaFieldModel(
        id=field_id,
        project_id=project_id,
        field_slug=new_slug,
        field_label=new_label,
        field_type=new_type,
        description=new_desc,
        is_required=new_required,
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
        cursor.execute(
            "SELECT id FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;",
            (project_id,),
        )
        remaining = cursor.fetchall()
        for idx, r in enumerate(remaining):
            conn.execute("UPDATE schema_fields SET order_index = ? WHERE id = ?;", (idx, r["id"]))

    return {"status": "deleted", "field_id": field_id}

@router.put("/fields", response_model=List[SchemaFieldModel])
async def replace_all_schema_fields(project_id: str, fields: List[SchemaFieldModel]):
    conn = get_project_connection(project_id)
    with conn:
        conn.execute("DELETE FROM schema_fields WHERE project_id = ?;", (project_id,))
        for idx, field in enumerate(fields):
            conn.execute(
                """
                INSERT INTO schema_fields (id, project_id, field_slug, field_label, field_type, description, is_required, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    field.id,
                    project_id,
                    field.field_slug,
                    field.field_label,
                    field.field_type,
                    field.description,
                    int(field.is_required),
                    idx,
                ),
            )

    return await get_project_schema(project_id)