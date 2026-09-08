import sqlite3
from typing import List, Optional, Tuple

def get_node_hierarchy_breadcrumb(conn: sqlite3.Connection, node_id: str) -> Tuple[str, List[str]]:
    query = """
    WITH RECURSIVE ancestors(id, document_id, parent_id, node_type, text_content, depth) AS (
        SELECT id, document_id, parent_id, node_type, text_content, 0
        FROM nodes
        WHERE id = ?
        UNION ALL
        SELECT n.id, n.document_id, n.parent_id, n.node_type, n.text_content, a.depth + 1
        FROM nodes n
        JOIN ancestors a ON n.id = a.parent_id
        WHERE a.depth < 50 AND a.parent_id IS NOT NULL
    )
    SELECT a.id, a.node_type, a.text_content, a.depth, d.filename as document_title
    FROM ancestors a
    JOIN documents d ON d.id = a.document_id
    ORDER BY a.depth DESC;
    """

    cursor = conn.cursor()
    cursor.execute(query, (node_id,))
    rows = cursor.fetchall()

    if not rows:
        return ("", [])

    doc_title = rows[0]["document_title"]
    headers = [row["text_content"] for row in rows]
    return (doc_title, headers)

def format_contextual_breadcrumb_string(conn: sqlite3.Connection, node_id: str) -> str:
    doc_title, hierarchy = get_node_hierarchy_breadcrumb(conn, node_id)
    if not doc_title and not hierarchy:
        return ""

    parts = [doc_title] + hierarchy
    return " > ".join(parts)

def validate_acyclic_parent(conn: sqlite3.Connection, node_id: str, new_parent_id: Optional[str]) -> bool:
    if new_parent_id is None:
        return True

    if node_id == new_parent_id:
        return False

    query = """
    WITH RECURSIVE ancestors(id, parent_id, depth) AS (
        SELECT id, parent_id, 0
        FROM nodes
        WHERE id = ?
        UNION ALL
        SELECT n.id, n.parent_id, a.depth + 1
        FROM nodes n
        JOIN ancestors a ON n.id = a.parent_id
        WHERE a.depth < 50 AND a.parent_id IS NOT NULL
    )
    SELECT id FROM ancestors WHERE id = ?;
    """
    cursor = conn.cursor()
    cursor.execute(query, (new_parent_id, node_id))
    match = cursor.fetchone()
    return match is None

def densify_order_indices(conn: sqlite3.Connection, document_id: str) -> None:
    query_select = """
    SELECT id FROM nodes
    WHERE document_id = ?
    ORDER BY order_index ASC, id ASC;
    """
    cursor = conn.cursor()
    cursor.execute(query_select, (document_id,))
    rows = cursor.fetchall()

    with conn:
        for idx, row in enumerate(rows):
            conn.execute(
                "UPDATE nodes SET order_index = ? WHERE id = ?;",
                (idx, row["id"]),
            )

def shift_order_indices(conn: sqlite3.Connection, document_id: str, start_index: int, delta: int) -> None:
    with conn:
        if delta > 0:
            conn.execute(
                """
                UPDATE nodes
                SET order_index = order_index + ?
                WHERE document_id = ? AND order_index >= ?;
                """,
                (delta, document_id, start_index),
            )
        elif delta < 0:
            conn.execute(
                """
                UPDATE nodes
                SET order_index = order_index + ?
                WHERE document_id = ? AND order_index >= ?;
                """,
                (delta, document_id, start_index),
            )
            densify_order_indices(conn, document_id)

def cascade_header_stale_status(conn: sqlite3.Connection, header_node_id: str) -> int:
    select_query = """
    WITH RECURSIVE descendants(id, depth) AS (
        SELECT id, 0
        FROM nodes
        WHERE parent_id = ?
        UNION ALL
        SELECT n.id, d.depth + 1
        FROM nodes n
        JOIN descendants d ON n.parent_id = d.id
        WHERE d.depth < 50
    )
    SELECT id FROM descendants;
    """
    cursor = conn.cursor()
    cursor.execute(select_query, (header_node_id,))
    rows = cursor.fetchall()
    if not rows:
        return 0

    descendant_ids = [row["id"] for row in rows]
    placeholders = ",".join("?" * len(descendant_ids))
    update_query = f"""
    UPDATE nodes
    SET embedding_status = 'stale'
    WHERE id IN ({placeholders})
      AND embedding_status = 'current';
    """
    with conn:
        update_cursor = conn.execute(update_query, descendant_ids)
        return update_cursor.rowcount