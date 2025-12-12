# tests/test_vector_databases.py

import unittest

from db.qdrant_store import QdrantVectorStore
from db.vector_store import VectorRecord, VectorStore
from embedding_manager.embedding_manager import EmbeddingManager
from embedding_manager.embedding_backend import StubEmbeddingModel, AllMiniLMl6V2EmbeddingModel, AllMpnetBaseV2, \
    EmbeddingModel
from typing import List, Dict, Any

async def bootstrap_demo_corpus(
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        user="user",
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

    # ensure collection exists
    dim = embedding_model.dim
    await vector_store.get_or_create_collection(collection, dim)

    # create a new database-agnostic data transfer object for each document/text we want to upload
    records: List[VectorRecord] = []
    for idx, (sentence, vector) in enumerate(zip(sentences, vectors)):
        # data to store
        metadata: Dict[str, Any] = {
            "text": sentence,
            "user_id": user,
        }
        records.append(
            VectorRecord(
                id=str(idx + 1),
                # needed to create unique point IDs (see upsert_points() above) fixme indexing from 0 is prone to accidental overwrites
                vector=vector,
                metadata=metadata,
            )
        )

    await vector_store.upsert_records(
        collection=collection,
        records=records,
    )
"""
IMPORTANT:
    These tests require a running Qdrant instance on port 6333.
    For local dev, you can start it with:

        docker run -p 6333:6333 qdrant/qdrant
"""

class TestQdrantEmbeddingManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Same wiring as your debug script
        self.store = QdrantVectorStore()
        self.models = {"pipeline_1": StubEmbeddingModel(dim=256),
                       "text_model_fast": AllMiniLMl6V2EmbeddingModel(),
                       "text_model_quality": AllMpnetBaseV2()}
        self.em = EmbeddingManager(embedding_models=self.models, vector_store=self.store)

    async def test_search_demo_corpus(self) -> None:
        """
        Integration-style test:
        - bootstrap demo corpus
        - run a semantic search
        - assert we get some reasonable-looking results back
        """
        corpus_id = "demo_corpus_20251212"
        embedding_model_id = "text_model_fast"
        await bootstrap_demo_corpus(embedding_model=self.models[embedding_model_id], vector_store= self.em.vector_store, collection=corpus_id)

        query = "I would like to learn more about RAG."  # sentence is present in bootstrapped demo_corpus
        result = await self.em.search_documents(
            user_id="user",
            corpus_id=corpus_id,
            embedding_model_id=embedding_model_id,
            query=query,
            k=5,
        )

        # basic shape checks
        self.assertEqual(result["query"], query)
        self.assertEqual(result["corpus_id"], corpus_id)
        self.assertGreater(len(result["results"]), 0, "Expected at least one search hit")

        # sanity check a couple of fields on the first hit
        first = result["results"][0]
        self.assertIn("score", first)
        self.assertIn("metadata", first)
        self.assertIn("text", first["metadata"])

    async def test_upsert_and_search_roundtrip(self) -> None:
        """
        - upsert some custom documents into a fresh corpus
        - search for them
        - assert the right docs come back
        """
        corpus_id = "test_upsert_corpus"
        user_id = "user_upsert"
        text = "RAG stands for retrieval augmented generation."

        documents = [
            {
                "id": "doc1",
                "text": text,
            },
        ]

        upsert_result = await self.em.upsert_documents(
            user_id=user_id,
            corpus_id=corpus_id,
            documents=documents,
        )

        # EmbeddingManager currently always returns "ok" on success
        self.assertEqual(upsert_result["status"], "ok")
        self.assertEqual(upsert_result["indexed_count"], len(documents))

        # Now search for something that should clearly hit doc1
        search_result = await self.em.search_documents(
            user_id=user_id,
            corpus_id=corpus_id,
            query=text,
            k=5,
        )

        self.assertGreater(
            len(search_result["results"]), 0, "Expected to retrieve at least one document"
        )

        # Check that our upserted text appears in the results
        matching_hits = [
            hit for hit in search_result["results"]
            if hit["metadata"]["text"] == text and hit["score"] == 1.0
        ]

        self.assertTrue(
            len(matching_hits) > 0,
            f"Expected a hit with text={text!r} and score=1.0"
        )

    # TODO: test failing upsert and failing search cases


if __name__ == "__main__":
    # Allows `python tests/db/test_vector_databases.py` as well as `python -m unittest`
    unittest.main()
