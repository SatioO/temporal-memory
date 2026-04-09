import os
from typing import Final, List, Optional

import httpx

from schema import EmbeddingProvider

API_URL = "https://openrouter.ai/api/v1/embeddings"
DEFAULT_MODEL = "openai/text-embedding-3-small"


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    name: Final[str] = "openrouter"
    dimensions: Final[int] = 1536

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY") or ""
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required")
        self.model = os.getenv("OPENROUTER_EMBEDDING_MODEL") or DEFAULT_MODEL

    async def embed(self, text: str) -> List[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                },
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"OpenRouter embedding failed ({response.status_code}): {response.text}"
            )

        data = response.json()
        return [item["embedding"] for item in data["data"]]
