import asyncio
import os
from typing import Final, List, Optional

from schema import EmbeddingProvider

MODEL_NAME = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")


class LocalEmbeddingProvider(EmbeddingProvider):
    name: Final[str] = "local"
    dimensions: Final[int] = 384

    def __init__(self) -> None:
        self._model = None  # lazy — loaded on first use

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        model = await self._get_model()

        # SentenceTransformer.encode is CPU-bound — run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True).tolist(),
        )
        return embeddings

    async def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "Install sentence-transformers for local embeddings: "
                "uv add sentence-transformers"
            )

        # Load model in thread pool — downloading/loading weights is blocking
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(
            None, lambda: SentenceTransformer(MODEL_NAME)
        )
        return self._model
