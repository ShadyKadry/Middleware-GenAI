# tests/test_vector_databases.py

import unittest

from db.qdrant_store import QdrantVectorStore
from embedding_manager.embedding_manager import EmbeddingManager
from embedding_manager.embedding_backend import StubEmbeddingModel


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
        self.model = StubEmbeddingModel(dim=256)
        self.em = EmbeddingManager(embedding_model=self.model, vector_store=self.store)

    async def test_search_demo_corpus(self) -> None:
        """
        Integration-style test:
        - bootstrap demo corpus
        - run a semantic search
        - assert we get some reasonable-looking results back
        """
        corpus_id = "demo_corpus"
        await self.store.bootstrap_demo_corpus(self.model, collection=corpus_id)

        query = "I would like to learn more about RAG."  # sentence is present in bootstrapped demo_corpus
        result = await self.em.search_documents(
            user_id="user",
            corpus_id=corpus_id,
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
