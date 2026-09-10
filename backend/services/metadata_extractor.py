import json
import sqlite3
from typing import Any, Callable, Dict, List, Optional
from openai import OpenAI

try:
    from backend.db.hierarchy import format_contextual_breadcrumb_string
    from backend.db.models import SchemaFieldModel, generate_json_schema_from_fields
except ImportError:
    from src.db.hierarchy import format_contextual_breadcrumb_string
    from src.db.models import SchemaFieldModel, generate_json_schema_from_fields

def get_project_schema_fields(conn: sqlite3.Connection, project_id: str) -> List[SchemaFieldModel]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC, id ASC;",
        (project_id,),
    )
    rows = cursor.fetchall()
    return [SchemaFieldModel(**dict(r)) for r in rows]

def get_target_chunks(conn: sqlite3.Connection, project_id: str, document_id: Optional[str] = None) -> List[sqlite3.Row]:
    cursor = conn.cursor()
    if document_id:
        cursor.execute(
            """
            SELECT n.id, n.document_id, n.parent_id, n.node_type, n.text_content, n.order_index
            FROM nodes n
            WHERE n.document_id = ? AND n.node_type = 'paragraph'
            ORDER BY n.order_index ASC;
            """,
            (document_id,),
        )
    else:
        cursor.execute(
            """
            SELECT n.id, n.document_id, n.parent_id, n.node_type, n.text_content, n.order_index
            FROM nodes n
            JOIN documents d ON n.document_id = d.id
            WHERE d.project_id = ? AND n.node_type = 'paragraph'
            ORDER BY d.order_index ASC, n.order_index ASC;
            """,
            (project_id,),
        )
    return cursor.fetchall()

def get_existing_chunk_metadata(conn: sqlite3.Connection, node_id: str) -> Dict[str, Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT field_id, field_value, user_edited FROM node_metadata WHERE node_id = ?;",
        (node_id,),
    )
    results: Dict[str, Dict[str, Any]] = {}
    for row in cursor.fetchall():
        results[row["field_id"]] = {
            "value": json.loads(row["field_value"]),
            "user_edited": bool(row["user_edited"]),
        }
    return results

def build_extraction_prompt(chunk_context: str, json_schema: Dict[str, Any]) -> List[Dict[str, str]]:
    system_msg = (
        "You are an expert metadata extraction assistant. "
        "Analyze the provided contextual document chunk and extract metadata conforming strictly to this JSON Schema:\n"
        f"{json.dumps(json_schema, indent=2)}\n\n"
        "Return ONLY a valid JSON object matching the schema."
    )
    user_msg = f"Document Breadcrumbs and Chunk:\n\n{chunk_context}"
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

def extract_metadata_for_chunk(
    client: OpenAI,
    model: str,
    chunk_context: str,
    json_schema: Dict[str, Any],
) -> Dict[str, Any]:
    messages = build_extraction_prompt(chunk_context, json_schema)
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)

def run_partitioned_metadata_extraction(
    conn: sqlite3.Connection,
    project_id: str,
    llm_client: OpenAI,
    llm_model: str,
    batch_size: int = 10,
    force_overwrite: bool = False,
    resume: bool = False,
    on_partition_start: Optional[Callable[[int, int, int, int], None]] = None,
    on_chunk_completed: Optional[Callable[[str, int, int], None]] = None,
    on_partition_completed: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    fields = get_project_schema_fields(conn, project_id)
    if not fields:
        return {"status": "no_fields", "total_chunks": 0, "total_partitions": 0}

    slug_to_field = {f.field_slug: f for f in fields}
    json_schema = generate_json_schema_from_fields(fields)

    chunks = get_target_chunks(conn, project_id)
    total_chunks = len(chunks)
    if total_chunks == 0:
        return {"status": "no_chunks", "total_chunks": 0, "total_partitions": 0}

    total_partitions = (total_chunks + batch_size - 1) // batch_size
    start_partition = 0

    cursor = conn.cursor()
    if resume:
        cursor.execute(
            """
            SELECT completed_partition FROM batch_checkpoints
            WHERE job_type = 'metadata'
            ORDER BY id DESC LIMIT 1;
            """
        )
        row = cursor.fetchone()
        if row and row["completed_partition"] is not None:
            start_partition = row["completed_partition"]
            if start_partition >= total_partitions:
                return {
                    "status": "already_completed",
                    "total_chunks": total_chunks,
                    "total_partitions": total_partitions,
                }

    with conn:
        conn.execute(
            """
            INSERT INTO batch_checkpoints (job_type, completed_partition, total_partitions, status, last_error, updated_at)
            VALUES ('metadata', ?, ?, 'in_progress', NULL, CURRENT_TIMESTAMP);
            """,
            (start_partition, total_partitions),
        )

    for p_idx in range(start_partition, total_partitions):
        chunk_start = p_idx * batch_size
        chunk_end = min(chunk_start + batch_size, total_chunks)
        partition_chunks = chunks[chunk_start:chunk_end]

        if on_partition_start:
            on_partition_start(p_idx, total_partitions, chunk_start, chunk_end)

        partition_updates: List[Dict[str, Any]] = []

        try:
            for c_offset, chunk_row in enumerate(partition_chunks):
                node_id = chunk_row["id"]
                breadcrumb = format_contextual_breadcrumb_string(conn, node_id)
                extracted_data = extract_metadata_for_chunk(
                    client=llm_client,
                    model=llm_model,
                    chunk_context=breadcrumb,
                    json_schema=json_schema,
                )

                existing_meta = get_existing_chunk_metadata(conn, node_id)
                node_field_updates = []

                for slug, field_obj in slug_to_field.items():
                    val = extracted_data.get(slug)
                    if val is None:
                        continue

                    current = existing_meta.get(field_obj.id)
                    if current and current["user_edited"] and not force_overwrite:
                        continue

                    node_field_updates.append(
                        (
                            node_id,
                            field_obj.id,
                            json.dumps(val),
                            0,
                        )
                    )

                partition_updates.append(
                    {"node_id": node_id, "updates": node_field_updates}
                )

                if on_chunk_completed:
                    on_chunk_completed(node_id, chunk_start + c_offset + 1, total_chunks)

            with conn:
                for chunk_update in partition_updates:
                    for node_id, field_id, serialized_val, user_edited in chunk_update["updates"]:
                        conn.execute(
                            """
                            INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(node_id, field_id) DO UPDATE SET
                                field_value = excluded.field_value,
                                user_edited = excluded.user_edited;
                            """,
                            (node_id, field_id, serialized_val, user_edited),
                        )

                conn.execute(
                    """
                    UPDATE batch_checkpoints
                    SET completed_partition = ?, status = 'in_progress', updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT MAX(id) FROM batch_checkpoints WHERE job_type = 'metadata');
                    """,
                    (p_idx + 1,),
                )

            if on_partition_completed:
                on_partition_completed(p_idx, total_partitions)

        except Exception as e:
            with conn:
                conn.execute(
                    """
                    UPDATE batch_checkpoints
                    SET status = 'failed', last_error = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = (SELECT MAX(id) FROM batch_checkpoints WHERE job_type = 'metadata');
                    """,
                    (str(e),),
                )
            raise

    with conn:
        conn.execute(
            """
            UPDATE batch_checkpoints
            SET completed_partition = ?, status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = (SELECT MAX(id) FROM batch_checkpoints WHERE job_type = 'metadata');
            """,
            (total_partitions,),
        )

    return {
        "status": "completed",
        "total_chunks": total_chunks,
        "total_partitions": total_partitions,
    }