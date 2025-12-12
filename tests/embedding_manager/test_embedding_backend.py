import unittest

from embedding_manager.embedding_backend import StubEmbeddingModel, AllMiniLMl6V2EmbeddingModel, AllMpnetBaseV2


class MyTestCase(unittest.TestCase):
    async def asyncSetUp(self) -> None:
        # Same wiring as your debug script
        self.models = {"pipeline_1": StubEmbeddingModel(dim=256),
                       "text_model_fast": AllMiniLMl6V2EmbeddingModel(),
                       "text_model_quality": AllMpnetBaseV2()}
    # Lightweight assert checks (fail fast if something is wrong)
    # assert len(embed_document("a")) == len(embed_document("b"))
    # assert get_registry().choose_for_request("text").id == "text_fast"
    # assert get_registry().choose_for_request("text", "text_quality").id == "text_quality"

    def test_explicit_quality_pipeline(self):
        print("\n=== Test 2: explicit 'text_quality' pipeline ===")
        text = ["This should use the high-quality model."]
        embedding_pipeline_id = "text_model_quality"

        vec = self.models[embedding_pipeline_id].embed(
            texts=text
        )
        print(f"Text: {text}")
        print(f"Vector length: {len(vec)}")
        print(f"First 5 values: {vec[:5]}")
        self.assertEqual(len(vec), self.models[embedding_pipeline_id].dim)

    # def test_pipeline_selection():
    #     print("\n=== Test 3: selection logic ===")
    #     registry = get_registry()
    #
    #     # A. No preferred id → should return the default ("text_fast")
    #     p_default = registry.choose_for_request(modality="text")
    #     print(f"Default text pipeline id: {p_default.id}")
    #
    #     # B. Explicit "text_quality" → should return that pipeline
    #     p_quality = registry.choose_for_request(
    #         modality="text",
    #         preferred_pipeline_id="text_quality",
    #     )
    #     print(f"Explicit text pipeline id: {p_quality.id}")
    #
    # def test_default_pipeline():
    #     print("=== Test 1: default text pipeline ===")
    #     text = "Middleware for GenAI."
    #     vec = embed_document(text)  # no pipeline id → uses default "text_fast"
    #     print(f"Text: {text}")
    #     print(f"Vector length: {len(vec)}")
    #     print(f"First 5 values: {vec[:5]}")


if __name__ == '__main__':
    unittest.main()
