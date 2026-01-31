from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence
from db.vector_store import VectorStore, VectorRecord
from .embedding_backend import EmbeddingModel


def build_access_constraints(user_id: str) -> dict:
    """
    Restrict read access to documents that belong to the provided user ID.
    """

    return {"user_id": user_id}


class EmbeddingManager:
    """
    High-level orchestration component for embedding and retrieval.

    Responsibilities:
      - generate embeddings using a configured embedding model
      - upsert and retrieve vectors through a VectorStore abstraction
        (Qdrant, pgvector, Milvus, etc.)
      - apply user-level access constraints during semantic search

    This class contains no backend-specific logic; individual VectorStore
    implementations handle their own filtering, storage, and querying.
    """

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
    ) -> None:
        self.embedding_model = embedding_model
        self.vector_store = vector_store  # the vector DB instance to use

    # ------------------------------
    # Public API
    # ------------------------------
    async def upsert_documents(
        self,
        user_id: str,
        corpus_id: str,
        documents: Sequence[Dict[str, Any]],
        collection_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        documents: List[{"id": str (optional), "text": str, ...extras}]
        """
        if not documents:
            return {
                "status": "ok",
                "indexed_count": 0,
                "requested_count": 0,
                "failed_ids": [],
            }

        # create vector embeddings
        texts = [d["text"] for d in documents]
        vectors = self.embedding_model.embed(texts)

        # make sure the collection to save into actually exists
        dim = len(vectors[0]) if vectors else self.embedding_model.dim
        collection = collection_name or corpus_id
        await self.vector_store.get_or_create_collection(collection, dim)

        # create a new database-agnostic data transfer object for each document/text we want to upload
        records: List[VectorRecord] = []
        for document, vector in zip(documents, vectors):
            # data to store
            metadata: Dict[str, Any] = {
                **document,
                "user_id": user_id,
                "corpus_id": corpus_id,
            }
            records.append(
                VectorRecord(
                    id=str(document["id"]) if "id" in document else None,
                    vector=vector,
                    metadata=metadata,
                )
            )

        # save new documents in database
        upsert_result = await self.vector_store.upsert_records(
            collection=collection,
            records=records,
        )

        return {
            "status": "ok" if upsert_result.status == "ok" else "error",
            "indexed_count": upsert_result.indexed_count,
            "requested_count": len(documents),
            "failed_ids": upsert_result.failed_ids,
        }

    async def search_documents(
        self,
        user_id: str,
        corpus_id: str,
        query: str,
        k: int = 5,
        collection_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        vectors = self.embedding_model.embed([query])
        query_vec = vectors[0]
        dim = len(query_vec) if query_vec is not None else self.embedding_model.dim

        collection = collection_name or corpus_id
        await self.vector_store.get_or_create_collection(collection, dim)

        # search for query_vector within database
        hits = await self.vector_store.search(
            collection=collection,  # some other backends might interpret this differently
            query_vector=query_vec,
            k=k,
            access_constraints=build_access_constraints(user_id),  # responsibility of each backend to enforce this
        )

        return {
            "query": query,
            "corpus_id": corpus_id,
            "results": [asdict(r) for r in hits],
        }
