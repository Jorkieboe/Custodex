import asyncio
import json
import logging
import re
import sys
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import openai

from backend.config import (
    get_embedding_endpoint,
    get_llm_endpoint,
    get_openai_api_key,
    load_config,
)
from backend.db.models import (
    NodeMetadataModel,
    SchemaFieldModel,
    generate_json_schema_from_fields,
)
from backend.services.project_manager import get_project_connection

logger = logging.getLogger("custodex.metadata")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [custodex.metadata]: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["metadata"])

class ChunkMetadataResponse(BaseModel):
    id: Optional[int] = None
    node_id: str
    field_id: str
    field_value: Any = None
    user_edited: bool = False
    field_slug: Optional[str] = None
    field_label: Optional[str] = None
    field_type: Optional[str] = None
    is_required: bool = False

class StartMetadataJobPayload(BaseModel):
    node_id: Optional[str] = None
    node_ids: Optional[List[str]] = None
    force_overwrite: bool = False
    resume: bool = False

def _normalize_model_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned.lower().startswith("gpts-"):
        cleaned = "gpt-" + cleaned[5:]
    elif cleaned.lower().startswith("gtp-"):
        cleaned = "gpt-" + cleaned[4:]
    return cleaned

def _get_llm_client_for_model(model_name: str) -> tuple[openai.OpenAI, str, str]:
    config = load_config()
    normalized_model = _normalize_model_name(model_name)
    api_key = get_openai_api_key(config)
    endpoint = get_llm_endpoint(config)

    is_openai_model = (
        normalized_model.lower().startswith("gpt-")
        or normalized_model.lower().startswith("o1")
        or normalized_model.lower().startswith("o3")
        or "api.openai.com" in endpoint.lower()
    )

    if is_openai_model and not endpoint.strip():
        endpoint = "https://api.openai.com/v1"

    masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else ("present" if api_key else "MISSING")
    logger.info("[LLM CONFIG] Model: '%s' (raw: '%s') | Endpoint: '%s' | API Key: %s", normalized_model, model_name, endpoint, masked_key)

    if is_openai_model:
        if not api_key:
            logger.warning("[AUTH WARNING] OpenAI model '%s' requested, but no OPENAI_API_KEY found in config or .env", normalized_model)
        client = openai.OpenAI(base_url=endpoint.rstrip("/"), api_key=api_key or "missing-key")
    else:
        client = openai.OpenAI(base_url=endpoint.rstrip("/"), api_key=api_key or "lm-studio")

    return client, normalized_model, endpoint

def _extract_metadata_for_chunk(
    client: openai.OpenAI,
    model_name: str,
    endpoint: str,
    chunk_text: str,
    node_id: str,
    doc_name: str,
    schema_fields: List[SchemaFieldModel],
) -> Dict[str, Any]:
    json_schema = generate_json_schema_from_fields(schema_fields)
    slug_to_field = {f.field_slug: f for f in schema_fields}

    system_prompt = (
        "You are an expert metadata extraction assistant for a Retrieval-Augmented Generation (RAG) system.\n"
        "Extract metadata from the provided document chunk strictly conforming to this JSON Schema:\n"
        f"{json.dumps(json_schema, indent=2)}\n\n"
        "Rules:\n"
        "1. Return ONLY a valid JSON object matching the schema.\n"
        "2. Do not include markdown codeblocks, explanations, or preface text."
    )

    user_prompt = f"Document: {doc_name}\n\nChunk Text:\n{chunk_text}"

    logger.info("=" * 60)
    logger.info("[METADATA CALL START] Node: %s | Doc: %s | Model: %s | Endpoint: %s", node_id, doc_name, model_name, endpoint)
    logger.info("[METADATA FIELDS TO EXTRACT] %s", [f.field_slug for f in schema_fields])
    logger.info("[CHUNK TEXT SAMPLE] %s", chunk_text[:180].replace("\n", " ") + ("..." if len(chunk_text) > 180 else ""))

    t0 = time.time()
    chosen_model = model_name
    if "api.openai.com" in endpoint.lower() and chosen_model in ("gpt-4.1-mini", "gpts-4.1-mini", "gtp-4.1-mini"):
        logger.info("[MODEL AUTO-MAP] OpenAI endpoint detected: re-mapping '%s' to standard 'gpt-4o-mini'", chosen_model)
        chosen_model = "gpt-4o-mini"

    logger.info("[METADATA CALL INITIATING] Model: %s | Endpoint: %s | Schema fields: %s", chosen_model, endpoint, [f.field_slug for f in schema_fields])

    try:
        response = client.chat.completions.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    except Exception as exc:
        logger.info("[RESPONSE FORMAT FALLBACK] Failed structured output; retrying with plain text: %s", exc)
        if "does not exist" in str(exc).lower() and ("4.1" in chosen_model):
            chosen_model = "gpt-4o-mini"
            logger.info("[RESPONSE FORMAT FALLBACK] Switched model to '%s'", chosen_model)
        response = client.chat.completions.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

    latency = round(time.time() - t0, 3)
    raw_content = response.choices[0].message.content or "{}"

    logger.info("[METADATA RAW OUTPUT] (Latency: %ss)\n%s", latency, raw_content)

    clean_json_str = raw_content.strip()
    if clean_json_str.startswith("```"):
        clean_json_str = re.sub(r"^```(?:json)?\n?", "", clean_json_str)
        clean_json_str = re.sub(r"\n?```$", "", clean_json_str).strip()

    try:
        extracted = json.loads(clean_json_str)
    except Exception as parse_err:
        logger.error("[METADATA PARSE ERROR] Failed to parse JSON: %s. Raw: %s", parse_err, clean_json_str)
        extracted = {}

    logger.info("[METADATA PARSED RESULT]\n%s", json.dumps(extracted, indent=2))
    logger.info("=" * 60)
    print(f"\n[METADATA EXTRACTION OUTPUT] Chunk {node_id} ({latency}s):\n{json.dumps(extracted, indent=2)}\n")

    return extracted

@router.get("/nodes/{node_id}/metadata", response_model=List[ChunkMetadataResponse])
async def get_node_metadata(project_id: str, node_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            m.id,
            ? as node_id,
            s.id as field_id,
            m.field_value,
            COALESCE(m.user_edited, 0) as user_edited,
            s.field_slug,
            s.field_label,
            s.field_type,
            COALESCE(s.is_required, 0) as is_required
        FROM schema_fields s
        LEFT JOIN node_metadata m ON (
            m.node_id = ? AND (m.field_id = s.id OR m.field_id = s.field_slug)
        )
        WHERE s.project_id = ?
        ORDER BY s.order_index ASC;
        """,
        (node_id, node_id, project_id),
    )
    rows = cursor.fetchall()
    results: List[ChunkMetadataResponse] = []

    for r in rows:
        val = r["field_value"]
        if val is not None:
            try:
                val = json.loads(val)
            except Exception:
                pass
        slug = r["field_slug"] if r["field_slug"] else r["field_id"]
        label = r["field_label"] if r["field_label"] else slug
        ftype = r["field_type"] if r["field_type"] else "string"
        results.append(
            ChunkMetadataResponse(
                id=r["id"],
                node_id=r["node_id"],
                field_id=r["field_id"],
                field_value=val,
                user_edited=bool(r["user_edited"]),
                field_slug=slug,
                field_label=label,
                field_type=ftype,
                is_required=bool(r["is_required"]),
            )
        )

    if not results:
        cursor.execute(
            """
            SELECT m.id, m.node_id, m.field_id, m.field_value, m.user_edited,
                   s.field_slug, s.field_label, s.field_type, COALESCE(s.is_required, 0) as is_required
            FROM node_metadata m
            LEFT JOIN schema_fields s ON (m.field_id = s.id OR m.field_id = s.field_slug)
            WHERE m.node_id = ?;
            """,
            (node_id,),
        )
        for r in cursor.fetchall():
            val = r["field_value"]
            if val is not None:
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            slug = r["field_slug"] if r["field_slug"] else r["field_id"]
            label = r["field_label"] if r["field_label"] else slug
            ftype = r["field_type"] if r["field_type"] else "string"
            results.append(
                ChunkMetadataResponse(
                    id=r["id"],
                    node_id=r["node_id"],
                    field_id=r["field_id"],
                    field_value=val,
                    user_edited=bool(r["user_edited"]),
                    field_slug=slug,
                    field_label=label,
                    field_type=ftype,
                    is_required=bool(r["is_required"]),
                )
            )

    return results

@router.put("/nodes/{node_id}/metadata")
@router.patch("/nodes/{node_id}/metadata")
@router.post("/nodes/{node_id}/metadata")
async def update_node_metadata(project_id: str, node_id: str, payload: Any = Body(...)):
    conn = get_project_connection(project_id)
    updates: Dict[str, Any] = {}
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and "field_id" in item:
                updates[item["field_id"]] = item.get("field_value", item.get("value", ""))
    elif isinstance(payload, dict):
        if "field_values" in payload and isinstance(payload["field_values"], dict):
            updates = payload["field_values"]
        elif "metadata" in payload and isinstance(payload["metadata"], dict):
            updates = payload["metadata"]
        else:
            updates = payload

    cursor = conn.cursor()
    cursor.execute("SELECT id, field_slug FROM schema_fields WHERE project_id = ?;", (project_id,))
    schema_rows = cursor.fetchall()
    slug_to_id: Dict[str, str] = {}
    id_to_id: Dict[str, str] = {}
    for r in schema_rows:
        slug_to_id[r["field_slug"]] = r["id"]
        slug_to_id[f"f_{r['field_slug']}"] = r["id"]
        id_to_id[r["id"]] = r["id"]
        id_to_id[f"f_{r['id']}"] = r["id"]

    cursor.execute("SELECT field_id FROM node_metadata WHERE node_id = ?;", (node_id,))
    existing_field_ids = {r["field_id"] for r in cursor.fetchall()}

    with conn:
        for key, raw_val in updates.items():
            if key in existing_field_ids:
                target_field_id = key
            elif key in slug_to_id and slug_to_id[key] in existing_field_ids:
                target_field_id = slug_to_id[key]
            elif key in id_to_id:
                target_field_id = id_to_id[key]
            elif key in slug_to_id:
                target_field_id = slug_to_id[key]
            else:
                target_field_id = key

            serialized = json.dumps(raw_val)
            conn.execute(
                """
                INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(node_id, field_id) DO UPDATE SET
                    field_value = excluded.field_value,
                    user_edited = 1;
                """,
                (node_id, target_field_id, serialized),
            )
    return {"status": "saved", "node_id": node_id}

@router.delete("/nodes/{node_id}/metadata")
async def delete_all_node_metadata(project_id: str, node_id: str):
    conn = get_project_connection(project_id)
    with conn:
        conn.execute("DELETE FROM node_metadata WHERE node_id = ?;", (node_id,))
    return {"status": "deleted", "node_id": node_id}

@router.post("/nodes/{node_id}/metadata/generate")
async def generate_single_node_metadata(project_id: str, node_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute("SELECT llm_model FROM projects WHERE id = ?;", (project_id,))
    proj_row = cursor.fetchone()
    model_name = proj_row["llm_model"] if proj_row else "gtp-4.1-mini"

    cursor.execute(
        """
        SELECT n.id, n.text_content, d.filename
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE n.id = ?;
        """,
        (node_id,),
    )
    node_row = cursor.fetchone()
    if not node_row:
        raise HTTPException(status_code=404, detail="Node not found")

    cursor.execute("SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;", (project_id,))
    fields = [SchemaFieldModel(**dict(r)) for r in cursor.fetchall()]
    if not fields:
        return {"status": "skipped", "reason": "No schema fields defined"}

    client, active_model, endpoint = _get_llm_client_for_model(model_name)
    extracted = _extract_metadata_for_chunk(
        client=client,
        model_name=active_model,
        endpoint=endpoint,
        chunk_text=node_row["text_content"],
        node_id=node_id,
        doc_name=node_row["filename"],
        schema_fields=fields,
    )

    with conn:
        for f in fields:
            if f.field_slug in extracted:
                val = extracted[f.field_slug]
                serialized = json.dumps(val)
                conn.execute(
                    """
                    INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(node_id, field_id) DO UPDATE SET
                        field_value = excluded.field_value,
                        user_edited = 0;
                    """,
                    (node_id, f.id, serialized),
                )

    return {"status": "completed", "node_id": node_id, "metadata": extracted}

@router.get("/metadata")
async def get_all_project_metadata(project_id: str):
    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT node_id
        FROM node_metadata m
        JOIN nodes n ON m.node_id = n.id
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ?;
        """,
        (project_id,),
    )
    rows = cursor.fetchall()
    return [{"node_id": r["node_id"]} for r in rows]

@router.post("/metadata/start")
@router.post("/metadata/generate")
async def start_metadata_generation(project_id: str, payload: StartMetadataJobPayload):
    if payload.node_id:
        return await generate_single_node_metadata(project_id, payload.node_id)

    conn = get_project_connection(project_id)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(n.id) as count
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.node_type = 'paragraph';
        """,
        (project_id,),
    )
    total = cursor.fetchone()["count"]
    return {
        "status": "started",
        "total_chunks": total,
        "completed_partitions": 0,
        "total_partitions": 1,
    }

@router.get("/metadata/stream")
async def stream_metadata_generation(project_id: str, force_overwrite: bool = Query(default=False)):
    logger.info(">>> [SSE ROUTE ENTER] GET /metadata/stream received for project_id=%s, force_overwrite=%s", project_id, force_overwrite)

    conn = get_project_connection(project_id)
    cursor = conn.cursor()

    cursor.execute("SELECT llm_model FROM projects WHERE id = ?;", (project_id,))
    proj_row = cursor.fetchone()
    model_name = proj_row["llm_model"] if proj_row else "gtp-4.1-mini"
    logger.info("[SSE ROUTE] Project LLM Model from DB: '%s'", model_name)

    cursor.execute(
        """
        SELECT n.id, n.text_content, d.filename
        FROM nodes n
        JOIN documents d ON n.document_id = d.id
        WHERE d.project_id = ? AND n.node_type = 'paragraph'
        ORDER BY d.order_index ASC, n.order_index ASC;
        """,
        (project_id,),
    )
    nodes_to_process = cursor.fetchall()
    logger.info("[SSE ROUTE] Total paragraph chunks to process: %d", len(nodes_to_process))

    cursor.execute("SELECT * FROM schema_fields WHERE project_id = ? ORDER BY order_index ASC;", (project_id,))
    schema_fields = [SchemaFieldModel(**dict(r)) for r in cursor.fetchall()]
    logger.info("[SSE ROUTE] Total schema fields configured: %d (%s)", len(schema_fields), [f.field_slug for f in schema_fields])

    async def event_generator() -> AsyncGenerator[str, None]:
        total_chunks = len(nodes_to_process)
        if total_chunks == 0 or not schema_fields:
            done_payload = json.dumps({"status": "completed", "completed_chunks": 0, "total_chunks": 0})
            yield f"event: complete\ndata: {done_payload}\n\n"
            return

        initial_payload = {
            "status": "running",
            "completed_chunks": 0,
            "total_chunks": total_chunks,
            "completed_partitions": 0,
            "total_partitions": 1,
        }
        yield f"event: progress\ndata: {json.dumps(initial_payload)}\n\n"

        client, active_model, endpoint = _get_llm_client_for_model(model_name)
        logger.info("[SSE METADATA RUN] Starting extraction on %s chunks using %s at %s", total_chunks, active_model, endpoint)

        completed = 0
        for node in nodes_to_process:
            node_id = node["id"]

            try:
                extracted = await asyncio.to_thread(
                    _extract_metadata_for_chunk,
                    client=client,
                    model_name=active_model,
                    endpoint=endpoint,
                    chunk_text=node["text_content"],
                    node_id=node_id,
                    doc_name=node["filename"],
                    schema_fields=schema_fields,
                )

                with conn:
                    for f in schema_fields:
                        if f.field_slug in extracted:
                            serialized = json.dumps(extracted[f.field_slug])
                            if force_overwrite:
                                conn.execute(
                                    """
                                    INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                                    VALUES (?, ?, ?, 0)
                                    ON CONFLICT(node_id, field_id) DO UPDATE SET
                                        field_value = excluded.field_value,
                                        user_edited = 0;
                                    """,
                                    (node_id, f.id, serialized),
                                )
                            else:
                                conn.execute(
                                    """
                                    INSERT INTO node_metadata (node_id, field_id, field_value, user_edited)
                                    VALUES (?, ?, ?, 0)
                                    ON CONFLICT(node_id, field_id) DO UPDATE SET
                                        field_value = CASE WHEN node_metadata.user_edited = 1 THEN node_metadata.field_value ELSE excluded.field_value END;
                                    """,
                                    (node_id, f.id, serialized),
                                )

                completed += 1
                progress_data = {
                    "status": "running",
                    "completed_chunks": completed,
                    "total_chunks": total_chunks,
                    "completed_partitions": 0,
                    "total_partitions": 1,
                    "current_chunk_id": node_id,
                }
                yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"

            except Exception as e:
                logger.error("[SSE METADATA ERROR] Error extracting chunk %s: %s", node_id, e)
                error_data = {
                    "status": "failed",
                    "completed_chunks": completed,
                    "total_chunks": total_chunks,
                    "last_error": str(e),
                }
                yield f"event: failure\ndata: {json.dumps(error_data)}\n\n"
                return

        final_data = {
            "status": "completed",
            "completed_chunks": completed,
            "total_chunks": total_chunks,
            "completed_partitions": 1,
            "total_partitions": 1,
        }
        yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )