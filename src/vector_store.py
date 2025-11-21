from typing import Any, Dict, List, Protocol, Sequence, Optional


class VectorStore(Protocol):
    """
    Abstract interface so we can swap Qdrant/pgvector/etc.
    """

    async def ensure_collection(self, name: str, dim: int) -> None:
        ...

    async def upsert_points(
            self,
            collection: str,
            vectors: Sequence[List[float]],
            payloads: Sequence[Dict[str, Any]],
            ids: Optional[Sequence[str]] = None,
    ) -> None:
        ...

    async def search(
            self,
            collection: str,
            query_vector: List[float],
            k: int,
            query_filter: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        ...
