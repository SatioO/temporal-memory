from abc import abstractmethod, ABC
from dataclasses import dataclass
from enum import Enum
from typing import List, Literal, Optional, TypedDict

ProviderType = Literal["agent-sdk", "anthropic", "gemini", "openrouter"]


@dataclass
class Session:
    id: str
    project: str
    cwd: str
    started_at: str
    ended_at: Optional[str] = None
    status: Literal["active", "completed", "abandoned"] = "active"
    observation_count: int = 0
    model: Optional[str] = None
    tags: Optional[str] = None


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
    provider: Optional["str"]
    bm25_weight: float
    vector_weight: float


@dataclass
class FallbackConfig:
    providers: List[ProviderType]


class EmbeddingProvider(ABC):
    name: str
    dimensions: int

    @abstractmethod
    async def embed(self, text: str):
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]):
        pass


class MemoryProvider(ABC):
    name: str

    @abstractmethod
    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        pass

    @abstractmethod
    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        pass


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


@dataclass
class CircuitBreakerSnapshot:
    state: CircuitBreakerState
    failures: int
    last_failure_at: Optional[float]
    opened_at: Optional[float]


@dataclass
class TeamConfig:
    team_id: str
    user_id: str
    mode: Literal["shared", "private"]


@dataclass
class OtelConfigSettings:
    service_name: str = "graphmind"
    service_version: str = "0.6.0"
    metrics_export_interval_ms: int = 30000
