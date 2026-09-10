import sqlite3

DDL_SCRIPT = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES nodes(id) ON DELETE SET NULL,
    node_type TEXT NOT NULL CHECK(node_type IN ('header', 'paragraph')),
    text_content TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    embedding_status TEXT NOT NULL DEFAULT 'missing' CHECK(embedding_status IN ('current', 'stale', 'missing'))
);

CREATE TABLE IF NOT EXISTS node_embeddings (
    node_id TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    embedding_blob BLOB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_fields (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    field_slug TEXT NOT NULL,
    field_label TEXT NOT NULL,
    field_type TEXT NOT NULL CHECK(field_type IN ('string', 'number', 'boolean', 'array[string]', 'array[number]', 'date')),
    description TEXT NOT NULL DEFAULT '',
    is_required INTEGER NOT NULL DEFAULT 0,
    order_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS node_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    field_id TEXT NOT NULL REFERENCES schema_fields(id) ON DELETE CASCADE,
    field_value TEXT NOT NULL,
    user_edited INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_node_field UNIQUE (node_id, field_id)
);

CREATE TABLE IF NOT EXISTS batch_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL CHECK(job_type IN ('metadata', 'embedding')),
    completed_partition INTEGER NOT NULL DEFAULT 0,
    total_partitions INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('in_progress', 'failed', 'completed')),
    last_error TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_nodes_doc_order ON nodes(document_id, order_index);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_metadata_node_field ON node_metadata(node_id, field_id);
CREATE INDEX IF NOT EXISTS idx_schema_fields_project ON schema_fields(project_id);
"""

def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(DDL_SCRIPT)