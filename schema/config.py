from dataclasses import dataclass
from typing import List, Literal, Optional

ProviderType = Literal["agent-sdk", "anthropic", "gemini", "openrouter"]


@dataclass
class ProviderConfig:
    provider: ProviderType
    model: str
    max_tokens: int


@dataclass
class AgentMemoryConfig:
    engine_url: str
    rest_port: int
    streams_port: int
    provider: str
    token_budget: int
    max_observations_per_session: int
    compression_model: str
    data_dir: str


@dataclass
class EmbeddingConfig:
    provider: Optional[str]
    bm25_weight: float
    vector_weight: float


@dataclass
class FallbackConfig:
    providers: List[ProviderType]


@dataclass
class TeamConfig:
    team_id: str
    user_id: str
    mode: Literal["shared", "private"]


@dataclass
class CloudBridgeConfig:
    enabled: bool
    memory_file_path: str
    line_budget: int
    project_path: Optional[str] = None


@dataclass
class OtelConfigSettings:
    service_name: str = "graphmind"
    service_version: str = "0.6.0"
    metrics_export_interval_ms: int = 30000
