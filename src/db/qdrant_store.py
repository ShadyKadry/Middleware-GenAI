import uuid
from typing import Any, Dict, List, Optional, Sequence
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
)

from db.vector_store import SearchResult, VectorRecord, VectorStore, UpsertResult
from qdrant_client.models import FieldCondition, MatchValue


# create Qdrant specific access filter
def build_access_filter(access_constraints: dict) -> Optional[Filter]:
    """
    Restrict read access to documents that belong to the provided constraints. (user_id only for now)
    """
    if not access_constraints or "user_id" not in access_constraints:
        raise PermissionError("No user_id in access constraints")  # will this break app execution? should be unreachable anyways...
    return Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=access_constraints["user_id"]),
            )
        ]
    )


class QdrantVectorStore(VectorStore):

    # IMPORTANT: make sure you have the Qdrant docker container up-and-running -> docker run -p 6333:6333 qdrant/qdrant (in terminal)
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = AsyncQdrantClient(host=host, port=port)

    async def get_or_create_collection(self, name: str, dim: int) -> None:
        # create_collection is idempotent; but might as well check existence first with get_collection
        try:
            await self.client.get_collection(name)
        except Exception:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dim,
                    distance=Distance.COSINE,
                ),
            )

    async def upsert_records(
        self,
        collection: str,
        records: List[VectorRecord],
        ) -> UpsertResult:
        # create new database entries
        points: List[PointStruct] = []
        for record in records:

            if record.id is None:
                # no ID provided: generate a random unique ID fixme record cannot be overwritten, replaced, or updated since same doc (without identifier) would result in different 'point_id'
                point_id = (str(uuid.uuid4()))
            else:
                # convert whatever ID is given into UUIDv5 based on its string fixme upsert/overwrite semantics only when ID is unique
                point_id = (str(uuid.uuid5(uuid.NAMESPACE_DNS, str(record.id))))

            points.append(PointStruct(id=point_id, vector=record.vector, payload=record.metadata))

        # upload them to the database
        update_result = await self.client.upsert(
            collection_name=collection,
            points=points,
            wait=True,
        )

        # normalize qdrant status to a plain lowercase string
        status_raw = getattr(update_result, "status", None)
        if status_raw is None and isinstance(update_result, dict):
            status_raw = update_result.get("status")

        # enum-safe: UpdateStatus.COMPLETED → "completed"
        status_str = getattr(status_raw, "value", status_raw)
        status_str = str(status_str).lower()

        is_ok = status_str in ("completed", "acknowledged")

        return UpsertResult(
            status="ok" if is_ok else "error",
            indexed_count=len(records) if is_ok else 0,
            failed_ids=[] if is_ok else [str(r.id) for r in records if r.id is not None],
            raw=update_result,
        )

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        k: int,
        access_constraints: dict,
    ) -> List[SearchResult]:
        response = await self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=k,
            query_filter=build_access_filter(access_constraints),  # create actual Qdrant filter implementation
            with_vectors=False,
            with_payload=True,
        )

        # obtain database entries that fulfill query (filtered due to attribute / within first k nearest / etc.)
        points = response.points

        # each p is a ScoredPoint
        results = []
        for p in points:
            results.append(
                SearchResult(
                    id=p.id,  # the unique UUID point ID
                    score=p.score,  # similarity score to query_vector
                    metadata=p.payload  # the created metadata incl. {text:"", idx:"", topic:"", user_id:""}
                )
            )

        return results

    #################################
    # ---- FOR DEMO PURPOSE ONLY ----
    #################################
