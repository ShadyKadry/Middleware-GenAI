import uuid
from typing import Any, Dict, List, Optional, Sequence
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
)
from vector_store import VectorStore


class QdrantVectorStore(VectorStore):
    # IMPORTANT: make sure you have the Qdrant docker container up-and-running -> docker run -p 6333:6333 qdrant/qdrant (in terminal)
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = AsyncQdrantClient(host=host, port=port)

    async def ensure_collection(self, name: str, dim: int) -> None:
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

    async def upsert_points(
        self,
        collection: str,
        vectors: Sequence[List[float]],
        payloads: Sequence[Dict[str, Any]],
        ids: Optional[Sequence[str]] = None,
    ) -> None:
        norm_ids: List[str] = []

        if ids is None:
            # no IDs provided: make deterministic UUIDs from collection + index
            for idx in range(len(vectors)):
                raw = f"{collection}--{idx}"
                norm_ids.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, raw)))
        else:
            # convert whatever is given into UUIDv5 based on its string
            for raw in ids:
                raw_str = str(raw)
                norm_ids.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_str)))

        # create new database entries
        points = [
            PointStruct(id=pid, vector=v, payload=p)
            for pid, v, p in zip(norm_ids, vectors, payloads)
        ]

        # upload them to the database
        await self.client.upsert(
            collection_name=collection,
            points=points,
            wait=True,
        )

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        k: int,
        query_filter: Optional[Filter] = None,
    ) -> List[Dict[str, Any]]:
        response = await self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=k,
            query_filter=query_filter,
            with_vectors=False,
            with_payload=True,
        )

        # obtain database entries that fulfill query (filtered due to attribute / within first k nearest / etc.)
        points = response.points

        # each p is a ScoredPoint
        results = []
        for p in points:
            results.append({
                "id": p.id,  # the unique UUID point ID
                "score": p.score,  # similarity score to query_vector
                "payload": p.payload,  # the created payload incl. {text:"", idx:"", topic:"", user_id:""}
            })

        return results

    # ---- FOR DEMO PURPOSE ----
    async def bootstrap_demo_corpus(
            self,
            embedding_model,
            user = "user",
            collection: str = "demo_corpus",
    ) -> None:
        """
        Creates a small demo corpus with pre-defined sentences.
        Is called once during 'middleware_application.py' startup to ingest some data into the Qdrant docker container.
        The resulting collection will only be available for queries with username: "user".
        """
        # dummy data to be stored in the database
        sentences = [
            "The Eiffel Tower is located in Paris, France.",
            "Python is a popular programming language for data science.",
            "The stock market can be very volatile during economic crises.",
            "Soccer is the most popular sport in many countries.",
            "Climate change is affecting weather patterns worldwide.",
            "Neural networks are a core technique in modern AI.",
            "Coffee is made from roasted coffee beans.",
            "The Great Wall of China is visible from certain satellites.",
            "Quantum computing uses qubits instead of classical bits.",
            "Mount Everest is the highest mountain above sea level.",
            "I would like to learn more about RAG.",
            "I would like to learn less about RAG.",
            "I would love to learn everything about RAG.",
            # ... extend this up if you like
        ]

        vectors = embedding_model.embed(sentences)
        dim = embedding_model.dim

        # ensure collection exists
        await self.ensure_collection(collection, dim)

        payloads: List[Dict[str, Any]] = []
        ids: List[str] = []

        for idx, sentence in enumerate(sentences):
            # we could also add any other key-value pair which might be beneficial (for filtering etc. [e.g. categorical values])
            payloads.append(
                {
                    "text": sentence,
                    "idx": idx,  # not necessary to append this for any logic ATM
                    "topic": "demo",  # TODO: should we configure this? is this important?
                    "user_id": user
                }
            )
            ids.append(str(idx+1)) # needed to create unique point IDs (see upsert_points() above)

        await self.upsert_points(
            collection=collection,
            vectors=vectors,
            payloads=payloads,
            ids=ids,
        )
