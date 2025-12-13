from __future__ import annotations

import hashlib
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Protocol, Sequence

import numpy as np



import os
from typing import List, Optional, Sequence

from dotenv import load_dotenv
from google import genai
from google.genai import types


# - - - - - - - - - - - - - - - - - - - - - Abstract class - - - - - - - - - - - - - - - - - - - - -
class EmbeddingModel(Protocol):
    """
    Minimal abstraction over 'something that embeds texts'.
    Extend this for actual embedding model implementations.
    """
    _dim: int

    @property
    @abstractmethod
    def dim(self) -> int:
        ...

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        ...


# - - - - - - - - - - - - - - - - - - - - - Implementations - - - - - - - - - - - - - - - - - - - - - TODO move actual implementations to separate classes?
class StubEmbeddingModel(EmbeddingModel):
    """

    Simple deterministic embedding for testing – produces fixed, random-looking
    vectors based only on a hash of the input text.

    Basic idea:
        Each input string is hashed with SHA-256, and the first 8 bytes of the
        hash are used as a seed for a NumPy random number generator. A
        `dim`-dimensional vector is then sampled from a standard normal
        distribution and normalized to unit length. This makes the embedding
        *deterministic* (the same text always produces the same vector) while
        still appearing random.

        However, different input strings produce completely different seeds, so
        their embeddings behave like independent random unit vectors. Any
        similarity between two texts is therefore accidental noise and not tied
        to their meaning.

    You should not expect:
        - semantically related or paraphrased texts to be close in vector space
        - “more” vs “less” or any other linguistic nuance to affect similarity
        - scores from this model to correlate with real semantic distance

    This is purely a convenience tool for testing pipelines, not a real
    embedding model.

    """

    def __init__(self, dim: int = 256):
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            seed = int.from_bytes(h[:8], "little")
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(self._dim)
            vec = vec / np.linalg.norm(vec)
            out.append(vec.astype(float).tolist())
        return out


# # Google Gemini embedding model - (IGNORED FOR NOW & OUT-COMMENTED IMPL NOT TESTED)
# class GeminiEmbeddingModel(EmbeddingModel):
#     def __init__(self, model_name: str = "text-embedding-004"):
#         # import google.generativeai as genai
#         #
#         # api_key = os.environ["GOOGLE_API_KEY"]
#         # genai.configure(api_key=api_key)
#         # self._client = genai
#         # self._model_name = model_name
#         # # You might hardcode dim or fetch from docs
#         # self._dim = 768  # example; set to actual
#         pass
#
#     @property
#     def dim(self) -> int:
#         # return self._dim
#         return 0
#
#     def embed(self, texts: Sequence[str]) -> List[List[float]]:
#         # adjust to the exact Gemini SDK API you’re using
#         # response = self._client.embed_content(
#         #     model=self._model_name,
#         #     content=list(texts),
#         # )
#         #
#         # # Example if response.embeddings is a list of embeddings:
#         # return [emb.values for emb in response.embeddings]
#         return [[0.0]]


load_dotenv()  # loads .env into environment

@dataclass
class GeminiEmbedding001(EmbeddingModel):
    """
    Gemini embedding implementation backed by the Google Gen AI SDK.

    Reads API key from environment:
      GEMINI_API_KEY or GOOGLE_API_KEY
    """
    model: str = "gemini-embedding-001"
    output_dimensionality: Optional[int] = None
    task_type: Optional[str] = "RETRIEVAL_DOCUMENT"  # embedding pipeline
    batch_size: int = 100
    _dim: int = 0

    def __post_init__(self) -> None:
        api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

        if not api_key:
            raise RuntimeError("Missing API key. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env")

        self._client = genai.Client(api_key=api_key)

    @property
    def dim(self) -> int:
        if self._dim <= 0:
            vec = self.embed(["_dimension_probe_"])[0]
            self._dim = len(vec)
        return self._dim

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []

        out: List[List[float]] = []
        cfg = (
            types.EmbedContentConfig(
                output_dimensionality=self.output_dimensionality,
                task_type=self.task_type,
            )
        )

        for i in range(0, len(texts), self.batch_size):
            chunk = list(texts[i : i + self.batch_size])

            result = self._client.models.embed_content(
                model=self.model,
                contents=chunk,
                config=cfg,
            )

            embeddings = getattr(result, "embeddings", None)
            if embeddings is None:
                raise RuntimeError("Gemini embed_content returned no embeddings.")

            for e in embeddings:
                if hasattr(e, "values"):
                    vec = list(e.values)
                elif isinstance(e, dict) and "values" in e:
                    vec = list(e["values"])
                else:
                    vec = list(e)

                out.append([float(x) for x in vec])

        if self._dim <= 0 and out:
            self._dim = len(out[0])

        return out
