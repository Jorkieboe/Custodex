import sqlite3
from pathlib import Path
from typing import Dict, Optional
from backend.db.connection import get_connection
from backend.db.migrations import init_db
from backend.db.models import ProjectModel

BASE_PROJECTS_DIR = Path(__file__).resolve().parent.parent.parent / "projects"

_open_connections: Dict[str, sqlite3.Connection] = {}

def get_project_db_path(project_id: str) -> Path:
    project_dir = BASE_PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir / f"{project_id}.sqlite"

def get_project_connection(project_id: str) -> sqlite3.Connection:
    if project_id in _open_connections:
        return _open_connections[project_id]

    db_path = get_project_db_path(project_id)
    conn = get_connection(db_path)
    init_db(conn)
    _open_connections[project_id] = conn
    return conn

def register_custom_connection(project_id: str, conn: sqlite3.Connection) -> None:
    _open_connections[project_id] = conn

def close_project_connection(project_id: str) -> None:
    if project_id in _open_connections:
        _open_connections[project_id].close()
        del _open_connections[project_id]

def ensure_project_record(conn: sqlite3.Connection, project_id: str, name: str = "Untitled Project", llm_model: str = "local-model", embedding_model: str = "text-embedding-nomic-embed-text-v1.5") -> ProjectModel:
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, llm_model, embedding_model, created_at, updated_at FROM projects WHERE id = ?;", (project_id,))
    row = cursor.fetchone()
    if row:
        return ProjectModel(**dict(row))

    project = ProjectModel(
        id=project_id,
        name=name,
        llm_model=llm_model,
        embedding_model=embedding_model
    )
    with conn:
        conn.execute(
            """
            INSERT INTO projects (id, name, llm_model, embedding_model)
            VALUES (?, ?, ?, ?);
            """,
            (project.id, project.name, project.llm_model, project.embedding_model)
        )
    return project