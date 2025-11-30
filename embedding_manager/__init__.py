from typing import List
from math import sin

from db.connection import get_connection

EMBEDDING_DIM = 768  # must match the vector(768) column in the DB


def _dummy_embedding(text: str) -> List[float]:
    """
    Very simple deterministic embedding function for the prototype.
    Not semantically meaningful, but enough to demonstrate pgvector.
    """
    values = [0.0] * EMBEDDING_DIM
    for i, ch in enumerate(text.encode("utf-8")):
        idx = i % EMBEDDING_DIM
        values[idx] += (ch % 32) / 32.0 * sin((i + 1) / 10.0)
    return values


def embed_document(document_id: int) -> None:
    """
    Read the document from the DB, compute one embedding for the full content,
    and store it as chunk_index = 0 in the embeddings table.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # fetch document content
                cur.execute(
                    "SELECT content FROM documents WHERE id = %s;",
                    (document_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Document {document_id} not found")

                content = row[0]
                embedding = _dummy_embedding(content)

                # convert embedding list to pgvector literal: "[0.1,0.2,...]"
                literal = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"

                # store in embeddings table as a single chunk (index 0)
                cur.execute(
                    """
                    INSERT INTO embeddings (document_id, chunk_index, chunk_text, embedding)
                    VALUES (%s, %s, %s, %s::vector);
                    """,
                    (document_id, 0, content, literal),
                )
    finally:
        conn.close()

def search_similar(query: str, top_k: int = 5):
    """
    Compute an embedding for the query text and return the closest chunks.
    Returns a list of dicts: {document_id, chunk_index, chunk_text, distance}.
    """
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                query_emb = _dummy_embedding(query)
                literal = "[" + ",".join(f"{x:.6f}" for x in query_emb) + "]"

                cur.execute(
                    """
                    SELECT
                        document_id,
                        chunk_index,
                        chunk_text,
                        embedding <-> %s::vector AS distance
                    FROM embeddings
                    ORDER BY distance
                    LIMIT %s;
                    """,
                    (literal, top_k),
                )
                rows = cur.fetchall()
                results = []
                for doc_id, chunk_idx, chunk_text, dist in rows:
                    results.append(
                        {
                            "document_id": doc_id,
                            "chunk_index": chunk_idx,
                            "chunk_text": chunk_text,
                            "distance": float(dist),
                        }
                    )
                return results
    finally:
        conn.close()
