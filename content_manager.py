from db.connection import get_connection


def create_document(title: str, content: str) -> int:
    """Insert a document and return its ID."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (title, content)
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (title, content),
                )
                doc_id = cur.fetchone()[0]
                return doc_id
    finally:
        conn.close()


def get_document(doc_id: int) -> dict | None:
    """Fetch a document by ID as a dict (or None if not found)."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, content, created_at, updated_at
                    FROM documents
                    WHERE id = %s;
                    """,
                    (doc_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                }
    finally:
        conn.close()
