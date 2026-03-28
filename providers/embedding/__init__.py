from typing import Optional

from config import detect_embedding_provider
from model import EmbeddingProvider

# TODO: add more embedding providers
def create_embedding_provider() -> Optional[EmbeddingProvider]:
    detected = detect_embedding_provider()

    if not detected:
        return None

    if detected == "openai":
        return None

    return None
