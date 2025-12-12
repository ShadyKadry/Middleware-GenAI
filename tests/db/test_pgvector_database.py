# tests/test_vector_databases.py

import unittest

from db.pgvector_store import PgVectorStore
from embedding_manager.embedding_manager import EmbeddingManager
from embedding_manager.embedding_backend import StubEmbeddingModel


"""
IMPORTANT:
    These tests require a running PgVector instance on port 5434.
    Please make sure you have all necessary docker containers available by running the following in repository root:
        docker compose up
"""

class TestQdrantEmbeddingManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # Same wiring as your debug script
        self.store = PgVectorStore()
        self.model = StubEmbeddingModel(dim=256)
        self.em = EmbeddingManager(embedding_model=self.model, vector_store=self.store)


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