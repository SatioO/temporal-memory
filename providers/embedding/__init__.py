from typing import Optional

from config import config
from schema import EmbeddingProvider

# TODO: add more embedding providers
def create_embedding_provider() -> Optional[EmbeddingProvider]:
    if not config.embedding_provider:
        return None

    if config.embedding_provider == "openai":
        return None

    return None
