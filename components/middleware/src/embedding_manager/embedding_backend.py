import hashlib
import os
from abc import abstractmethod
from typing import Callable, Dict, List, Optional, Protocol, Sequence

from dotenv import load_dotenv
from google import genai

import numpy as np


# - - - - - - - - - - - - - - - - - - - - - Abstract class - - - - - - - - - - - - - - - - - - - - -
class EmbeddingModel(Protocol):
    """
    Minimal abstraction over 'something that embeds texts'.
    Extend this for actual embedding model implementations.
    """

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


# Google Gemini embedding model - (IGNORED FOR NOW & OUT-COMMENTED IMPL NOT TESTED)
class GeminiEmbeddingModel(EmbeddingModel):
    def __init__(self, model_name: str = "gemini-embedding-001"):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Missing GEMINI_API_KEY in environment variable.")

        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name
        self._dim: Optional[int] = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise ValueError("Embedding dimension unknown until first embed call.")
        return self._dim

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        # adjust to the exact Gemini SDK API you’re using
        # response = self._client.embed_content(
        #     model=self._model_name,
        #     content=list(texts),
        # )
        #
        # # Example if response.embeddings is a list of embeddings:
        # return [emb.values for emb in response.embeddings]
        if not texts:
            return []

        try:
            response = self._client.models.embed_content(
                model=self._model_name,
                contents=list(texts),
            )
        except TypeError:
            response = self._client.models.embed_content(
                model=self._model_name,
                content=list(texts),
            )

        embeddings = getattr(response, "embeddings", None)
        if embeddings is None:
            embeddings = getattr(response, "embedding", None)
        if embeddings is None and isinstance(response, dict):
            embeddings = response.get("embeddings") or response.get("embedding")
        if embeddings is None:
            embeddings = [response]
        if not isinstance(embeddings, list):
            embeddings = [embeddings]

        vectors: List[List[float]] = []
        for emb in embeddings:
            values = _extract_embedding_values(emb)
            if values is None:
                raise ValueError("Unexpected embedding response format.")
            vectors.append([float(x) for x in values])

        if vectors and self._dim is None:
            self._dim = len(vectors[0])

        return vectors


def _extract_embedding_values(obj) -> Optional[List[float]]:
    if isinstance(obj, dict):
        if "values" in obj:
            return obj["values"]
        if "embedding" in obj:
            return obj["embedding"]

    for attr in ("values", "embedding"):
        if hasattr(obj, attr):
            return getattr(obj, attr)

    if isinstance(obj, list):
        return obj

    return None


DEFAULT_EMBEDDING_MODEL_ID = "gemini-embedding-001"

_MODEL_REGISTRY: Dict[str, Callable[[], EmbeddingModel]] = {
    "stub-256": lambda: StubEmbeddingModel(dim=256),
    "gemini-embedding-001": lambda: GeminiEmbeddingModel(model_name="gemini-embedding-001"),
}

_MODEL_CACHE: Dict[str, EmbeddingModel] = {}


def list_embedding_model_ids() -> List[str]:
    return list(_MODEL_REGISTRY.keys())


def get_embedding_model(model_id: str) -> EmbeddingModel:
    if model_id not in _MODEL_REGISTRY:
        raise ValueError(f"Unknown embedding model: {model_id}")

    if model_id not in _MODEL_CACHE:
        _MODEL_CACHE[model_id] = _MODEL_REGISTRY[model_id]()

    return _MODEL_CACHE[model_id]
