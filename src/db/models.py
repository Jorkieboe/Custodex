import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

NodeType = Literal["header", "paragraph"]
EmbeddingStatus = Literal["current", "stale", "missing"]
FieldType = Literal["string", "number", "boolean", "array[string]", "array[number]", "date"]
JobType = Literal["metadata", "embedding"]
BatchStatus = Literal["in_progress", "failed", "completed"]

def generate_uuid() -> str:
    return str(uuid.uuid4())

class ProjectModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_uuid)
    name: str
    llm_model: str
    embedding_model: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DocumentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_uuid)
    project_id: str
    filename: str
    file_type: str
    order_index: int
    created_at: Optional[datetime] = None

class NodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_uuid)
    document_id: str
    parent_id: Optional[str] = None
    node_type: NodeType
    text_content: str
    order_index: int
    embedding_status: EmbeddingStatus = "missing"

class NodeEmbeddingModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: str
    embedding_blob: bytes
    updated_at: Optional[datetime] = None

class SchemaFieldModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=generate_uuid)
    project_id: str
    field_slug: str
    field_label: str
    field_type: FieldType
    description: str = ""
    is_required: bool = False
    order_index: int

class NodeMetadataModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    node_id: str
    field_id: str
    field_value: str
    user_edited: bool = False

class BatchCheckpointModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    job_type: JobType
    completed_partition: int = 0
    total_partitions: int = 0
    status: BatchStatus = "in_progress"
    last_error: Optional[str] = None
    updated_at: Optional[datetime] = None

def generate_json_schema_from_fields(fields: List[SchemaFieldModel]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []

    sorted_fields = sorted(fields, key=lambda f: f.order_index)

    for field in sorted_fields:
        field_def: Dict[str, Any] = {}

        if field.description:
            field_def["description"] = field.description

        if field.field_type == "string":
            field_def["type"] = "string"
        elif field.field_type == "number":
            field_def["type"] = "number"
        elif field.field_type == "boolean":
            field_def["type"] = "boolean"
        elif field.field_type == "date":
            field_def["type"] = "string"
            field_def["format"] = "date"
        elif field.field_type == "array[string]":
            field_def["type"] = "array"
            field_def["items"] = {"type": "string"}
        elif field.field_type == "array[number]":
            field_def["type"] = "array"
            field_def["items"] = {"type": "number"}

        properties[field.field_slug] = field_def

        if field.is_required:
            required.append(field.field_slug)

    schema: Dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }

    if required:
        schema["required"] = required

    return schema