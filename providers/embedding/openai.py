import os
from typing import Final, List, Optional
from schema import EmbeddingProvider

API_URL = "https://api.openai.com/v1/embeddings"


class OpenAIProvider(EmbeddingProvider):
    name: Final[str] = "openai"
    dimensions: Final[int] = 1536

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")

    async def embed(self, text: str):
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: List[str]):
        pass
