# src/db/pgvector_store.py

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from db.vector_store import SearchResult, UpsertResult, VectorRecord, VectorStore


def _vector_literal(vec: List[float]) -> str:
    """Convert a Python list to pgvector literal: [0.123456,0.234567,...]."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


class PgVectorStore(VectorStore):
    """
    VectorStore implementation backed by PostgreSQL + pgvector.

    We store all vectors in a single table `pg_vectors` and distinguish logical
    collections via the `collection` column.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        dim: int = 256,
    ) -> None:
        # DSN for your Dockerized pgvector instance
        self.dsn = dsn or "postgresql://middleware_user:middleware_pwd@localhost:5434/middleware_genai"
        # We fix the pgvector dimension at 256 to match StubEmbeddingModel(dim=256)
        self.dim = dim

    # ------------------------------------------------------------------ #
    # Collection management
    # ------------------------------------------------------------------ #
    async def get_or_create_collection(self, collection_name: str, dim: int) -> None:
        """
        Ensure the backing table exists.

        We ignore `collection_name` here and keep a single table `pg_vectors`,
        separated by the `collection` column.
        """
        await asyncio.to_thread(self._ensure_table)

    def _ensure_table(self) -> None:
        ddl = f"""
        CREATE TABLE IF NOT EXISTS pg_vectors (
            id TEXT PRIMARY KEY,
            collection TEXT NOT NULL,
            vector vector({self.dim}) NOT NULL,
            metadata JSONB NOT NULL
        );
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    # ------------------------------------------------------------------ #
    # Upsert
    # ------------------------------------------------------------------ #
    async def upsert_records(
        self,
        collection: str,
        records: List[VectorRecord],
    ) -> UpsertResult:
        return await asyncio.to_thread(self._upsert_sync, collection, records)

    def _upsert_sync(
        self,
        collection: str,
        records: List[VectorRecord],
    ) -> UpsertResult:
        if not records:
            return UpsertResult(
                status="ok",
                indexed_count=0,
                failed_ids=[],
                raw={},
            )

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                for record in records:
                    # Try to derive an id:
                    rec_id: Optional[str] = None
                    if record.id is not None:
                        rec_id = str(record.id)
                    elif isinstance(record.metadata, dict) and "id" in record.metadata:
                        rec_id = str(record.metadata["id"])
                    else:
                        # Fallback: hash metadata → stable-ish id for this prototype
                        rec_id = str(hash(json.dumps(record.metadata, sort_keys=True)))

                    vec_literal = _vector_literal(record.vector)

                    cur.execute(
                        """
                        INSERT INTO pg_vectors (id, collection, vector, metadata)
                        VALUES (%s, %s, %s::vector, %s::jsonb)
                        ON CONFLICT (id) DO UPDATE
                        SET collection = EXCLUDED.collection,
                            vector     = EXCLUDED.vector,
                            metadata   = EXCLUDED.metadata
                        """,
                        (rec_id, collection, vec_literal, json.dumps(record.metadata)),
                    )

            conn.commit()

        return UpsertResult(
            status="ok",
            indexed_count=len(records),
            failed_ids=[],
            raw={},
        )

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    async def search(
        self,
        collection: str,
        query_vector: List[float],
        k: int,
        access_constraints: Dict[str, Any],
    ) -> List[SearchResult]:
        return await asyncio.to_thread(
            self._search_sync,
            collection,
            query_vector,
            k,
            access_constraints or {},
        )

    def _search_sync(
        self,
        collection: str,
        query_vector: List[float],
        k: int,
        access_constraints: Dict[str, Any],
    ) -> List[SearchResult]:
        user_id: Optional[str] = access_constraints.get("user_id")

        vec_literal = _vector_literal(query_vector)

        sql = """
        SELECT
            id,
            metadata,
            (vector <-> %s::vector) AS distance
        FROM pg_vectors
        WHERE collection = %s
        """
        params: List[Any] = [vec_literal, collection]

        # Enforce user-level access if provided
        if user_id is not None:
            sql += " AND metadata->>'user_id' = %s"
            params.append(str(user_id))

        sql += " ORDER BY vector <-> %s::vector LIMIT %s"
        params.extend([vec_literal, k])

        results: List[SearchResult] = []

        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        for row in rows:
            distance = float(row["distance"])  # l2 distance, lower is better
            similarity_score = 1.0 / (1.0 + distance)  # higher is better -> range [0..1]

            results.append(
                SearchResult(
                    id=row["id"],
                    score=similarity_score,
                    metadata=row["metadata"],
                )
            )

        return results

