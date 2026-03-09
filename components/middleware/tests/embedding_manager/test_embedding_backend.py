import unittest

from embedding_manager.embedding_backend import StubEmbeddingModel


class MyTestCase(unittest.TestCase):
    async def asyncSetUp(self) -> None:
        self.models = {"pipeline_1": StubEmbeddingModel(dim=256)}

    def test_explicit_quality_pipeline(self):
        print("\n=== Test: explicit pipeline ===")
        self.models = {"pipeline_1": StubEmbeddingModel(dim=256)}
        text = ["This should use the \"high-quality\" model."]
        embedding_pipeline_id = "pipeline_1"

        vec = self.models[embedding_pipeline_id].embed(
            texts=text
        )
        print(f"Text: {text}")
        print(f"Vector length: {len(vec)}")
        print(f"First 5 values: {vec[:5]}")
        self.assertEqual(len(vec[0]), self.models[embedding_pipeline_id].dim)


if __name__ == '__main__':
    unittest.main()
