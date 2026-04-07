from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Literal, Optional

from schema.base import Model


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


class HookType(str, Enum):
    SESSION_START = "session_start"
    PROMPT_SUBMIT = "prompt_submit"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    POST_TOOL_FAILURE = "post_tool_failure"
    PRE_COMPACT = "pre_compact"
    SUBAGENT_START = "subagent_start"
    SUBAGENT_STOP = "subagent_stop"
    NOTIFICATION = "notification"
    TASK_COMPLETED = "task_completed"
    STOP = "stop"
    SESSION_END = "session_end"


@dataclass(frozen=True)
class HookPayload(Model):
    hook_type: HookType
    session_id: str
    project: str
    cwd: str
    timestamp: str
    data: Any = None


@dataclass(frozen=True)
class RawObservation(Model):
    id: str
    session_id: str
    timestamp: str
    hook_type: HookType
    tool_name: Optional[str] = None
    tool_input: Optional[Any] = None
    tool_output: Optional[Any] = None
    user_prompt: Optional[str] = None
    assistant_response: Optional[str] = None
    raw: Any = None


@dataclass(frozen=True)
class CompressedObservation(Model):
    id: str
    session_id: str
    timestamp: str
    type: ObservationType
    title: str
    facts: list
    narrative: str
    concepts: list
    files: list
    importance: int
    subtitle: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class FileHistory(Model):
    file: str
    observations: list[CompressedObservation]


@dataclass(frozen=True)
class SessionSummary(Model):
    id: str
    session_id: str
    project: str
    created_at: str
    title: str
    narrative: str
    key_decisions: list[str]
    files_modified: list[str]
    concepts: list[str]
    observation_count: int
    confidence: Optional[float] = None


@dataclass(frozen=True)
class Session(Model):
    id: str
    project: str
    cwd: str
    started_at: str
    ended_at: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    observation_count: int = 0
    model: Optional[str] = None
    tags: Optional[str] = None


@dataclass(frozen=True)
class Memory(Model):
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


@dataclass(frozen=True)
class ProjectTopConcepts(Model):
    concept: str
    frequency: str


@dataclass(frozen=True)
class ProjectTopFiles(Model):
    file: str
    frequency: str


@dataclass(frozen=True)
class ProjectProfile(Model):
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


@dataclass(frozen=True)
class ContextBlock(Model):
    type: Literal["summary", "observation", "memory"]
    content: str
    tokens: int
    recency: int


@dataclass(frozen=True)
class CircuitBreakerSnapshot(Model):
    state: CircuitBreakerState
    failures: int
    last_failure_at: Optional[float] = None
    opened_at: Optional[float] = None


@dataclass(frozen=True)
class SearchResult(Model):
    obs_id: int
    score: int
    session_id: str


@dataclass
class HybridSearchResult(Model):
    observation: CompressedObservation
    bm25_score: float
    vector_score: float
    combined_score: float
    session_id: str


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
