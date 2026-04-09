import os
from typing import Optional

from schema import EmbeddingProvider
from providers.embedding.openai import OpenAIEmbeddingProvider
from providers.embedding.openrouter import OpenRouterEmbeddingProvider
from providers.embedding.local import LocalEmbeddingProvider


def _detect_embedding_provider() -> Optional[str]:
    forced = os.getenv("EMBEDDING_PROVIDER")
    if forced:
        return forced

    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("VOYAGE_API_KEY"):
        return "voyage"
    if os.getenv("COHERE_API_KEY"):
        return "cohere"
    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.getenv("LOCAL_EMBEDDING_MODEL") or os.getenv("EMBEDDING_PROVIDER") == "local":
        return "local"

    return None


def create_embedding_provider() -> Optional[EmbeddingProvider]:
    detected = _detect_embedding_provider()
    if not detected:
        return None

    if detected == "openai":
        return OpenAIEmbeddingProvider(os.getenv("OPENAI_API_KEY"))
    if detected == "openrouter":
        return OpenRouterEmbeddingProvider(os.getenv("OPENROUTER_API_KEY"))
    if detected == "local":
        return LocalEmbeddingProvider()

    return None
