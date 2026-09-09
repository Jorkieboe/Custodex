from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.models import ProjectModel, generate_uuid
from src.services.project_manager import ensure_project_record, get_project_connection

router = APIRouter(prefix="/api/projects", tags=["projects"])

class CreateProjectPayload(BaseModel):
    name: str
    llm_model: str = "local-model"
    embedding_model: str = "text-embedding-nomic-embed-text-v1.5"

@router.post("", response_model=ProjectModel)
async def create_project(payload: CreateProjectPayload):
    project_id = generate_uuid()
    conn = get_project_connection(project_id)
    project = ensure_project_record(
        conn,
        project_id=project_id,
        name=payload.name,
        llm_model=payload.llm_model,
        embedding_model=payload.embedding_model,
    )
    return project

@router.get("/{project_id}", response_model=ProjectModel)
async def get_project(project_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ?;", (project_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectModel(**dict(row))