# src/db/pgvector_store.py

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from db.vector_store import SearchResult, UpsertResult, VectorRecord, VectorStore


def _vector_literal(vec: List[float]) -> str:
    """Convert a Python list to pgvector literal: [0.123456,0.234567,...]."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


class PgVectorStore(VectorStore):
    """
    VectorStore implementation backed by PostgreSQL + pgvector.

    Creates a new table for each collection we store.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
    ) -> None:
        # DSN for the dockerized pgvector instance
        self.dsn = dsn or "postgresql://middleware_user:middleware_pwd@localhost:5434/middleware_genai"

    # ------------------------------------------------------------------ #
    # Collection management
    # ------------------------------------------------------------------ #
    async def get_or_create_collection(self, collection_name: str, dim: int) -> None:
        """
        Ensure the backing table exists.
        """

        await asyncio.to_thread(self._ensure_table, collection_name, dim)

    def _ensure_table(self, collection_name: str, dim: int) -> None:
        table_id = sql.Identifier(collection_name)  # design decision: each collection has its own table

        ddl = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {table} (
                id       TEXT PRIMARY KEY,
                vector   vector({dim}) NOT NULL,
                metadata JSONB NOT NULL
            );
        """).format(
            table=table_id,
            dim=sql.Literal(dim),
        )

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

        table_name = sql.Identifier(collection)
        insert_sql = sql.SQL("""
            INSERT INTO {table} (id, vector, metadata)
            VALUES (%s, %s::vector, %s::jsonb)
            ON CONFLICT (id) DO UPDATE
            SET vector   = EXCLUDED.vector,
                metadata = EXCLUDED.metadata
        """).format(table=table_name)

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                for record in records:
                    # Try to derive an id:
                    if record.id is not None:
                        rec_id = str(record.id)
                    elif isinstance(record.metadata, dict) and "id" in record.metadata:
                        rec_id = str(record.metadata["id"])
                    else:
                        # Fallback: hash metadata → stable-ish id for this prototype
                        rec_id = str(hash(json.dumps(record.metadata, sort_keys=True)))

                    md = record.metadata if isinstance(record.metadata, dict) else {}
                    md.setdefault("allowed_users", [])
                    md.setdefault("allowed_roles", [])
                    if not isinstance(md["allowed_users"], list) or not isinstance(md["allowed_roles"], list):
                        raise ValueError("metadata.allowed_users and metadata.allowed_roles must be lists")

                    vec_literal = _vector_literal(record.vector)

                    cur.execute(insert_sql, (rec_id, vec_literal, json.dumps(md)))

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
        access_identifier: Dict[str, Any],
    ) -> List[SearchResult]:
        return await asyncio.to_thread(
            self._search_sync,
            collection,
            query_vector,
            k,
            access_identifier or {},
        )

    def _search_sync(
        self,
        collection: str,
        query_vector: List[float],
        k: int,
        access_identifier: Dict[str, Any],
    ) -> List[SearchResult]:
        user_id: Optional[str] = access_identifier.get("user_id")
        user_role: Optional[str] = access_identifier.get("user_role")

        vec_literal = _vector_literal(query_vector)
        table_id = sql.Identifier(collection)

        search_sql = sql.SQL("""
            SELECT
                id,
                metadata,
                (vector <=> %s::vector) AS distance
            FROM {table}
            WHERE TRUE
        """).format(table=table_id)
        params: List[Any] = [vec_literal]

        # Enforce user-level access if provided (if an entry does not contain 'allowed_users' or 'allowed_roles' -> NULL -> treated as false)
        if user_id is not None or user_role is not None:
            clauses = []
            if user_id is not None:
                clauses.append(sql.SQL("metadata->'allowed_users' ? %s"))
                params.append(str(user_id))

            if user_role is not None:
                clauses.append(sql.SQL("metadata->'allowed_roles' ? %s"))
                params.append(str(user_role))

            # Add: AND ( ... OR ... )
            search_sql = search_sql + sql.SQL(" AND (") + sql.SQL(" OR ").join(clauses) + sql.SQL(")")

        # Order/limit (cosine distance via <=>)
        search_sql = search_sql + sql.SQL(" ORDER BY vector <=> %s::vector LIMIT %s")
        params.extend([vec_literal, k])

        results: List[SearchResult] = []

        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(search_sql, params)
                rows = cur.fetchall()

        for row in rows:
            results.append(
                SearchResult(
                    id=row["id"],
                    score=float(row["distance"]),
                    metadata=row["metadata"],
                )
            )

        return results
