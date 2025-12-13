import unittest

from embedding_manager.embedding_backend import GeminiEmbedding001


class EmbeddingModelTest(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.embedding_pipeline = GeminiEmbedding001()

    def test_explicit_quality_pipeline(self):
        print("\n=== Test 2: explicit 'text_quality' pipeline ===")
        text = "This should use the high-quality model."
        vec = self.embedding_pipeline.embed(text)
        print(f"Text: {text}")
        print(f"Vector length: {len(vec[0])}")

        self.assertEqual(len(vec[0]), self.embedding_pipeline.dim)


if __name__ == '__main__':
    unittest.main()
