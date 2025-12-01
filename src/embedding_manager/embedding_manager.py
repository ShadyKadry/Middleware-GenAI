
from typing import Any, Dict, List, Optional, Sequence
from qdrant_client.models import Filter, FieldCondition, MatchValue
from db.vector_store import VectorStore
from embedding_backend import EmbeddingModel


class EmbeddingManager:
    """
    Handles:
      - embedding text via an embedding pipeline
      - storing vectors in a vector store (Qdrant, etc.)
      - semantic search with user-based access control
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_model = embedding_model
        self.vector_store = vector_store  # the vector DB to use TODO use multiple DBs

    # ------------------------------
    # Public API
    # ------------------------------

    async def index_documents(
        self,
        user_id: str,
        corpus_id: str,
        documents: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        documents: List[{"id": str (optional), "text": str, ...extras}]
        """
        texts = [d["text"] for d in documents]
        vectors = self.embedding_model.embed(texts)

        dim = self.embedding_model.dim
        await self.vector_store.ensure_collection(corpus_id, dim)

        payloads: List[Dict[str, Any]] = []
        ids: List[str] = []

        # create a new payload for each document/text we want to upload TODO other DBs than Qdrant might expect something different
        for doc in documents:
            payload = dict(doc)
            payload["user_id"] = user_id
            payload["corpus_id"] = corpus_id
            payloads.append(payload)
            if "id" in doc:
                ids.append(str(doc["id"]))

        ids_list: Optional[List[str]] = ids if ids else None

        # save new documents in database
        await self.vector_store.upsert_points(
            collection=corpus_id,
            vectors=vectors,
            payloads=payloads,
            ids=ids_list,
        )

        return {
            "status": "ok",
            "indexed_count": len(documents),
        }

    async def semantic_search(
        self,
        user_id: str,
        corpus_id: str,
        query: str,
        k: int = 5,
    ) -> Dict[str, Any]:
        vectors = self.embedding_model.embed([query])
        query_vec = vectors[0]
        dim = self.embedding_model.dim

        await self.vector_store.ensure_collection(corpus_id, dim)

        query_filter = self._build_read_filter(user_id)

        # search for query_vector within database
        hits = await self.vector_store.search(
            collection=corpus_id,
            query_vector=query_vec,
            k=k,
            query_filter=query_filter,
        )

        return {
            "query": query,
            "corpus_id": corpus_id,
            "results": hits,
        }

    # ------------------------------
    # Internal helpers
    # ------------------------------

    def _build_read_filter(self, user_id: str) -> Optional[Filter]:
        """
        Restrict read access to documents that belong to the provided user ID.
        """
        return Filter(
            must=[
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                )
            ]
        )

