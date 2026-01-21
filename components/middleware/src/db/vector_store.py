from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Sequence, Optional


@dataclass
class VectorRecord:
    """
    A standard, backend-agnostic representation of a single vectorized document.

    Attributes:
        id (str):
            Optional external ID provided by the caller. Backends may use this to derive their
            own internal primary key, or ignore it and generate their own IDs.

        vector (List[float]):
            The embedding vector associated with the record. All vectors stored in
            the same collection must have identical dimensionality.

        metadata (Dict[str, Any]):
            Arbitrary document metadata (e.g. user_id, corpus_id, text, tags, timestamps).
            Backends may store this as JSON, key–value payloads, table columns, etc.
            Must be JSON-serializable to guarantee compatibility across vector DBs.
    """
    id: Optional[str]  # currently optional -> might require refactor when real-world documents are uploaded
    vector: List[float]
    metadata: Dict[str, Any]


@dataclass
class SearchResult:
    id: str
    score: float
    metadata: Dict[str, Any]


@dataclass
class UpsertResult:
    status: str
    indexed_count: int
    failed_ids: List[str] = field(default_factory=list)
    raw: Optional[Any] = None  # raw backend result for debugging



class VectorStore(Protocol):
    """
    Abstract interface for vector storage backends (Qdrant, pgvector, Milvus, Chroma, etc.).

    Implementations must:
      - manage collections/indexes,
      - store and update vector records,
      - perform vector search with optional filtering,
      - return structured results.

    Nothing in this interface should expose backend-specific concepts (payloads,
    partitions, segments, HNSW params, etc.).
    """

    async def get_or_create_collection(self, collection_name: str, dim: int) -> None:
        """
        Create or validate a logical vector collection/index.

        Args:
            collection_name (str):
                Name of the collection / table / index in which vectors will be stored.
                Meaning is backend-specific:
                  • Qdrant → collection
                  • pgvector → table
                  • Milvus → collection
                  • Chroma → collection

            dim (int):
                Dimensionality of vectors to be stored.
                Backends must ensure that the target collection:
                    - exists, and
                    - has a vector field of the correct size.
                If the collection does not exist, it must be created.
        """
        ...

    async def upsert_records(
            self,
            collection: str,
            records: List[VectorRecord],
    ) -> UpsertResult:
        """
        Insert or update vector records in the backend.

        Args:
            collection (str):
                The target logical collection/index/table.

            records (List[VectorRecord]):
                List of VectorRecord objects containing:
                    - id: unique stable identifier
                    - vector: corresponding vector (should match the order of `vectors`)
                    - metadata: arbitrary fields (e.g. text/user/corpus/etc.)

                The backend must:
                    • insert a new record if `id` does not exist, OR
                    • update the existing record with matching `id`.

                Implementations may:
                    - merge metadata,
                    - fully replace existing metadata,
                    - store metadata as JSON or scalar fields,
                    - normalize IDs as required.

        Notes:
            - `vectors` and `records` MUST refer to the same items in the same order.
            - This API avoids assuming the backend uses "payloads" (Qdrant term),
              or "entities" (Milvus term), or JSONB columns (pgvector).
        """
        ...

    async def search(
            self,
            collection: str,
            query_vector: List[float],
            k: int,
            access_constraints: dict,  # additional/optional 'query_filter' for further restriction?
    ) -> List[SearchResult]:
        """
        Perform a vector similarity search with optional filtering.

        Args:
            collection (str):
                The logical collection/index/table to query.

            query_vector (List[float]):
                The embedding vector representing the search query.

            k (int):
                Maximum number of nearest results to return.

            access_constraints (dict):
                A filter object describing application-level restrictions
                (e.g. {"user_id": "..."}).
                Backends must translate this into their own filtering mechanism:
                    • Qdrant → Filter(must=[FieldCondition(...)])
                    • Milvus → boolean expression string
                    • pgvector → SQL WHERE clause

                If empty or None, perform an unrestricted similarity search.

        Returns:
            List[Dict[str, Any]]:
                A list of structured search results.
                Each result MUST contain:
                    - "id": record ID
                    - "score": similarity/distance score
                    - "metadata": dict of stored metadata

                Additional backend-specific fields SHOULD NOT be included.

        Notes:
            - Search semantics (cosine, dot product, L2) depend on backend configuration.
            - Backends must ensure that access constraints are enforced securely.
        """
        ...
