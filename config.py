import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from schema import AgentMemoryConfig, CloudBridgeConfig, EmbeddingConfig, FallbackConfig, ProviderConfig, TeamConfig


DATA_DIR = os.path.join(os.path.expanduser("~"), ".graphmind")


def _load_env_file(path=".env"):
    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if (
                (value.startswith('"') and value.endswith('"')) or
                (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]

            os.environ.setdefault(key, value)


def _get_env(key: str, default=None, required: bool = False):
    value = os.getenv(key, default)

    if required and value is None:
        raise RuntimeError(f"Missing required env variable: {key}")

    return value


def safe_int(value: str | None, fallback: int) -> int:
    if value == None:
        return fallback

    try:
        return int(value, 10)
    except (TypeError, ValueError):
        return fallback


def safe_float(value: str | None, fallback: int) -> int:
    if value == None:
        return fallback

    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _detect_provider() -> ProviderConfig:
    max_tokens = safe_int(os.getenv("MAX_TOKENS"), 4096)

    if os.getenv("ANTHROPIC_API_KEY"):
        return ProviderConfig(
            provider="anthropic",
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=max_tokens,
        )

    if os.getenv("GEMINI_API_KEY"):
        return ProviderConfig(
            provider="gemini",
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            max_tokens=max_tokens,
        )

    if os.getenv("OPENROUTER_API_KEY"):
        return ProviderConfig(
            provider="openrouter",
            model=os.getenv(
                "OPENROUTER_MODEL",
                "anthropic/claude-sonnet-4-20250514",
            ),
            max_tokens=max_tokens,
        )

    return ProviderConfig(
        provider="agent-sdk",
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
    )


@lru_cache
def load_config() -> AgentMemoryConfig:
    _load_env_file()

    provider = _detect_provider()
    return AgentMemoryConfig(
        engine_url=_get_env(
            "III_ENGINE_URL", "ws://localhost:49134"),
        rest_port=safe_int(_get_env("III_REST_PORT"), "3111"),
        streams_port=safe_int(_get_env("III_STREAMS_PORT"), "3112"),
        provider=provider,
        token_budget=safe_int(_get_env("TOKEN_BUDGET"), "2000"),
        max_observations_per_session=safe_int(
            _get_env("MAX_OBS_PER_SESSION"), "500"
        ),
        compression_model=provider.model,
        data_dir=DATA_DIR,
    )


def load_embedding_config() -> EmbeddingConfig:
    bm25_weight = safe_float(os.getenv("BM25_WEIGHT"), "0.4")
    vector_weight = safe_float(os.getenv("VECTOR_WEIGHT"), "0.6")

    bm25_weight = 0.4 if bm25_weight < 0 else min(bm25_weight, 1)
    vector_weight = 0.6 if vector_weight < 0 else min(vector_weight, 1)

    provider = os.getenv("EMBEDDING_PROVIDER")

    return EmbeddingConfig(
        provider=provider,
        bm25_weight=bm25_weight,
        vector_weight=vector_weight,
    )


VALID_PROVIDERS = ["anthropic",
                   "gemini",
                   "openrouter",
                   "agent-sdk",]


def load_fallback_config() -> FallbackConfig:
    raw = os.getenv("FALLBACK_PROVIDERS", "")
    providers = [p.strip() for p in raw.split(",") if p in VALID_PROVIDERS]
    return FallbackConfig(providers=providers)


def detect_embedding_provider() -> Optional[str]:
    forced = os.getenv("EMBEDDING_PROVIDER")

    if forced:
        return forced

    if (os.getenv("GEMINI_API_KEY")):
        return "gemini"
    if (os.getenv("OPENAI_API_KEY")):
        return "openai"
    if (os.getenv("VOYAGE_API_KEY")):
        return "voyage"
    if (os.getenv("COHERE_API_KEY")):
        return "cohere"
    if (os.getenv("OPENROUTER_API_KEY")):
        return "openrouter"

    return None


def load_team_config() -> Optional[TeamConfig]:
    team_id = os.getenv("TEAM_ID")
    user_id = os.getenv("USER_ID")

    if not team_id or user_id:
        return None

    mode = os.getenv("USER_MODE")

    return TeamConfig(
        team_id=team_id,
        user_id=user_id,
        mode="shared" if mode == "shared" else "private"
    )


def load_claude_bridge_config() -> CloudBridgeConfig:
    enabled = os.getenv("CLAUDE_MEMORY_BRIDGE", "false").lower() == "true"
    project_path = os.getenv("CLAUDE_PROJECT_PATH")
    line_budget = safe_int(os.getenv("CLAUDE_MEMORY_LINE_BUDGET"), 200)

    memory_file_path = ""

    if enabled and project_path is not None:
        safe_path = re.sub(r"[/\\]", "-", project_path)
        safe_path = re.sub(r"^-", "", safe_path)
        memory_file_path = (
            Path.home()
            / ".claude"
            / "projects"
            / safe_path
            / "memory"
            / "MEMORY.md"
        )

    return CloudBridgeConfig(
        enabled=enabled,
        memory_file_path=memory_file_path,
        line_budget=line_budget,
        project_path=project_path
    )
