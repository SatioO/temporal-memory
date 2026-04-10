import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

ProviderType = Literal["agent-sdk", "anthropic",
                       "gemini", "openrouter", "openai"]

_VALID_PROVIDERS: frozenset = frozenset(
    {"anthropic", "gemini", "openrouter", "agent-sdk", "openai"})

_DEFAULT_DATA_DIR: str = str(Path.home() / ".graphmind")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            os.environ.setdefault(key, value)


def _safe_int(value: str | None, fallback: int) -> int:
    if value is None:
        return fallback
    try:
        return int(value, 10)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: str | None, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float, lo: float, hi: float, fallback: float) -> float:
    return value if lo <= value <= hi else fallback


def _detect_provider() -> tuple[ProviderType, str]:
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic", os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    if os.getenv("OPENAI_API_KEY"):
        return "openai", os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

    if os.getenv("GEMINI_API_KEY"):
        return "gemini", os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    if os.getenv("OPENROUTER_API_KEY"):
        return "openrouter", os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")

    return "agent-sdk", "claude-haiku-4-5-20251001"


def _detect_embedding_provider() -> Optional[str]:
    forced = os.getenv("EMBEDDING_PROVIDER")
    if forced:
        return forced
    for env_key, name in [
        ("GEMINI_API_KEY",     "gemini"),
        ("OPENAI_API_KEY",     "openai"),
        ("VOYAGE_API_KEY",     "voyage"),
        ("COHERE_API_KEY",     "cohere"),
        ("OPENROUTER_API_KEY", "openrouter"),
    ]:
        if os.getenv(env_key):
            return name
    return None


def _build_memory_path(project_path: str) -> str:
    # Replace path separators with dashes — preserve the leading dash that comes
    # from the opening slash so the folder name matches what Claude Code creates.
    # e.g. /Users/foo/bar → -Users-foo-bar  (Claude Code uses this exact format)
    safe = re.sub(r"[/\\]", "-", project_path)
    return str(Path.home() / ".claude" / "projects" / safe / "memory" / "MEMORY.md")


# ---------------------------------------------------------------------------
# Sub-config types — kept as parameter types for providers / functions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderConfig:
    provider: ProviderType
    model: str
    max_tokens: int


@dataclass(frozen=True)
class FallbackConfig:
    providers: List[ProviderType]


@dataclass(frozen=True)
class TeamConfig:
    team_id: str
    user_id: str
    mode: Literal["shared", "private"]


@dataclass(frozen=True)
class CloudBridgeConfig:
    enabled: bool
    memory_file_path: str
    line_budget: int
    project_path: Optional[str] = None


@dataclass(frozen=True)
class ConsolidatePipelineConfig:
    enabled: bool
    decay_days: int
    interval: int


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: Optional[str]
    bm25_weight: float
    vector_weight: float


@dataclass(frozen=True)
class OtelConfigSettings:
    service_name: str = "graphmind"
    service_version: str = "0.6.0"
    metrics_export_interval_ms: int = 30000


# ---------------------------------------------------------------------------
# Root config — flat, frozen, eager-loaded via AppConfig.from_env()
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    # Engine
    engine_url: str
    rest_port: int
    streams_port: int

    # Provider
    provider: ProviderType
    model: str
    max_tokens: int

    # Memory
    token_budget: int
    max_observations_per_session: int
    data_dir: str

    # Embedding
    embedding_provider: Optional[str]
    bm25_weight: float
    vector_weight: float

    # Fallback
    fallback_providers: List[str]

    # Consolidation
    consolidation_enabled: bool
    consolidation_decay_days: int
    consolidation_interval_min: int

    # Team
    team_id: Optional[str]
    user_id: Optional[str]
    team_mode: Literal["shared", "private"]

    # Claude Bridge
    claude_bridge_enabled: bool
    claude_bridge_memory_file_path: str
    claude_bridge_line_budget: int
    claude_project_path: Optional[str]

    def __post_init__(self) -> None:
        if not (1 <= self.rest_port <= 65535):
            raise EnvironmentError(
                f"III_REST_PORT out of range: {self.rest_port}")
        if not (1 <= self.streams_port <= 65535):
            raise EnvironmentError(
                f"III_STREAMS_PORT out of range: {self.streams_port}")
        if not (0.0 <= self.bm25_weight <= 1.0):
            raise EnvironmentError(
                f"BM25_WEIGHT must be 0–1, got {self.bm25_weight}")
        if not (0.0 <= self.vector_weight <= 1.0):
            raise EnvironmentError(
                f"VECTOR_WEIGHT must be 0–1, got {self.vector_weight}")

    # ------------------------------------------------------------------
    # Convenience views — map flat fields back to sub-config param types
    # ------------------------------------------------------------------

    @property
    def provider_config(self) -> ProviderConfig:
        return ProviderConfig(provider=self.provider, model=self.model, max_tokens=self.max_tokens)

    @property
    def fallback_config(self) -> FallbackConfig:
        return FallbackConfig(providers=self.fallback_providers)

    @property
    def team_config(self) -> Optional[TeamConfig]:
        if not self.team_id or not self.user_id:
            return None
        return TeamConfig(team_id=self.team_id, user_id=self.user_id, mode=self.team_mode)

    @property
    def bridge_config(self) -> CloudBridgeConfig:
        return CloudBridgeConfig(
            enabled=self.claude_bridge_enabled,
            memory_file_path=self.claude_bridge_memory_file_path,
            line_budget=self.claude_bridge_line_budget,
            project_path=self.claude_project_path,
        )

    @property
    def consolidate_pipeline_config(self) -> ConsolidatePipelineConfig:
        return ConsolidatePipelineConfig(
            enabled=self.consolidation_enabled,
            decay_days=self.consolidation_decay_days,
            interval=self.consolidation_interval_min * 60,  # convert minutes → seconds
        )

    @classmethod
    def from_env(cls) -> "AppConfig":
        _load_env_file()

        provider, model = _detect_provider()
        max_tokens = _safe_int(os.getenv("MAX_TOKENS"), 4096)
        bm25_weight = _clamp(_safe_float(
            os.getenv("BM25_WEIGHT"),   0.4), 0.0, 1.0, 0.4)
        vector_weight = _clamp(_safe_float(
            os.getenv("VECTOR_WEIGHT"), 0.6), 0.0, 1.0, 0.6)

        raw_fallback = os.getenv("FALLBACK_PROVIDERS", "")
        fallback_providers = [p.strip() for p in raw_fallback.split(
            ",") if p.strip() in _VALID_PROVIDERS]

        bridge_enabled = os.getenv(
            "CLAUDE_MEMORY_BRIDGE", "false").lower() == "true"
        project_path = os.getenv("CLAUDE_PROJECT_PATH") or os.getcwd()
        memory_file_path = _build_memory_path(
            project_path) if bridge_enabled else ""

        consolidation_enabled = os.getenv(
            "CONSOLIDATION_ENABLED", "false").lower() == "true"
        consolidation_decay_days = _safe_int(
            os.getenv("CONSOLIDATION_DECAY_DAYS"), 30)
        consolidation_interval_min = _safe_int(
            os.getenv("CONSOLIDATION_INTERVAL"), 30)

        return cls(
            engine_url=os.getenv("III_ENGINE_URL", "ws://localhost:49134"),
            rest_port=_safe_int(os.getenv("III_REST_PORT"), 3111),
            streams_port=_safe_int(os.getenv("III_STREAMS_PORT"), 3112),
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            token_budget=_safe_int(os.getenv("TOKEN_BUDGET"), 2000),
            max_observations_per_session=_safe_int(
                os.getenv("MAX_OBS_PER_SESSION"), 500),
            data_dir=os.getenv("DATA_DIR", _DEFAULT_DATA_DIR),
            embedding_provider=_detect_embedding_provider(),
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            fallback_providers=fallback_providers,
            team_id=os.getenv("TEAM_ID"),
            user_id=os.getenv("USER_ID"),
            team_mode="shared" if os.getenv(
                "USER_MODE") == "shared" else "private",
            claude_bridge_enabled=bridge_enabled,
            claude_bridge_memory_file_path=memory_file_path,
            claude_bridge_line_budget=_safe_int(
                os.getenv("CLAUDE_MEMORY_LINE_BUDGET"), 200),
            claude_project_path=project_path,
            consolidation_enabled=consolidation_enabled,
            consolidation_decay_days=consolidation_decay_days,
            consolidation_interval_min=consolidation_interval_min
        )
