from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel


class ObservationType(str, Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    COMMAND_RUN = "command_run"
    SEARCH = "search"
    WEB_FETCH = "web_fetch"
    CONVERSATION = "conversation"
    ERROR = "error"
    DECISION = "decision"
    DISCOVERY = "discovery"
    SUBAGENT = "subagent"
    NOTIFICATION = "notification"
    TASK = "task"
    OTHER = "other"


class MemoryType(str, Enum):
    PATTERN = "pattern"
    PREFERENCE = "preference"
    ARCHITECTURE = "architecture"
    BUG = "bug"
    WORKFLOW = "workflow"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CompressedObservation(BaseModel):
    id: str
    session_id: str
    timestamp: str
    type: ObservationType
    title: str
    subtitle: Optional[str]
    facts: list[str]
    narrative: str
    concepts: list[str]
    files: list[str]
    importance: int
    confidence: Optional[float]


class Session(BaseModel):
    id: str
    project: str
    cwd: str
    started_at: str
    ended_at: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    observation_count: int = 0
    model: Optional[str] = None
    tags: Optional[str] = None


class Memory(BaseModel):
    id: str
    created_at: str
    updated_at: str

    type: MemoryType

    title: str
    content: str

    concepts: List[str]
    files: List[str]
    session_ids: List[str]

    strength: float
    version: int

    parent_id: Optional[str] = None
    supersedes: Optional[List[str]] = None
    related_ids: Optional[List[str]] = None
    source_observation_ids: Optional[List[str]] = None

    is_latest: bool
    forget_after: Optional[str] = None


class ProjectTopConcepts(BaseModel):
    concept: str
    frequency: str


class ProjectTopFiles(BaseModel):
    file: str
    frequency: str


class ProjectProfile(BaseModel):
    project: str
    updated_at: str
    top_concepts: List[ProjectTopConcepts]
    top_files: List[ProjectTopFiles]
    conventions: List[str]
    common_errors: List[str]
    recent_activity: List[str]
    session_count: int
    total_observations: int
    summary: Optional[str] = None


class ContextBlock(BaseModel):
    type: Literal["summary", "observation", "memory"]
    content: str
    tokens: int
    recency: int


class CircuitBreakerSnapshot(BaseModel):
    state: CircuitBreakerState
    failures: int
    last_failure_at: Optional[float] = None
    opened_at: Optional[float] = None


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
