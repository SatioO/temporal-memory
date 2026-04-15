from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

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


class GraphNodeType(str, Enum):
    FILE = "file"
    FUNCTION = "function"
    CONCEPT = "concept"
    ERROR = "error"
    DECISION = "decision"
    PATTERN = "pattern"
    LIBRARY = "library"
    PERSON = "person"
    ROLE = "role"
    PROJECT = "project"
    PREFERENCE = "preference"
    LOCATION = "location"
    ORGANIZATION = "organization"
    EVENT = "event"


class GraphEdgeType(str, Enum):
    USES = "uses"
    IMPORTS = "imports"
    MODIFIES = "modifies"
    CAUSES = "causes"
    FIXES = "fixes"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    WORKS_AT = "works_at"
    PREFERS = "prefers"
    BLOCKED_BY = "blocked_by"
    CAUSED_BY = "caused_by"
    OPTIMIZES_FOR = "optimizes_for"
    REJECTED = "rejected"
    AVOIDS = "avoids"
    LOCATED_IN = "located_in"
    SUCCEEDED_BY = "succeeded_by"
    SUPERSEDES = "supersedes"
    HAS_ROLE = "has_role"


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
    version: int
    parent_id: Optional[str] = None
    supersedes: Optional[List[str]] = None
    related_ids: Optional[List[str]] = None
    is_latest: bool = True
    forget_after: Optional[str] = None


@dataclass(frozen=True)
class SemanticMemory(Model):
    id: str
    fact: str
    confidence: float
    source_session_ids: List[str]
    source_memory_ids: List[str]
    access_count: int
    last_accessed_at: str
    strength: float
    created_at: str
    updated_at: str
    # Extraction metadata — populated during consolidation
    category: Optional[str] = None          # architecture, code_pattern, error_fix, …
    scope: str = "project"                  # "project" | "universal"
    retrieval_hint: Optional[str] = None    # when to surface this fact
    superseded_by: Optional[str] = None     # id of the replacing SemanticMemory


@dataclass(frozen=True)
class ProceduralMemory(Model):
    id: str
    name: str
    steps: List[str]
    trigger_condition: str
    frequency: int
    source_session_ids: List[str]
    strength: float
    created_at: str
    updated_at: str
    # Rich procedure structure — populated during consolidation
    confidence: float = 0.5                 # reliability score across observed executions
    preconditions: Optional[List[str]] = None   # what must be true before step 1
    postconditions: Optional[List[str]] = None  # observable state after completion
    failure_modes: Optional[List[str]] = None   # "failure → recovery" pairs
    scope: str = "project"                  # "project" | "universal"
    retrieval_hint: Optional[str] = None    # when to surface this procedure


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


@dataclass(frozen=True)
class GraphNode(Model):
    id: str
    type: GraphNodeType
    name: str
    properties: Dict[str, Any]
    source_obs_ids: List[str]
    created_at: str
    updated_at: Optional[str] = None
    aliases: Optional[List[str]] = None
    stale: Optional[bool] = None


@dataclass(frozen=True)
class EdgeContext(Model):
    reasoning: Optional[str] = None
    sentiment: Optional[str] = None
    alternatives: Optional[List[str]] = None
    situational_factors: Optional[List[str]] = None
    confidence: Optional[float] = None


@dataclass(frozen=True)
class GraphEdge(Model):
    id: str
    type: "GraphEdgeType"
    source_node_id: str
    target_node_id: str
    weight: float
    source_obs_ids: List[str]
    created_at: str

    tcommit: Optional[str] = None
    tvalid: Optional[str] = None
    tvalid_end: Optional[str] = None
    context: Optional[EdgeContext] = None
    version: Optional[int] = None
    superseded_by: Optional[str] = None
    is_latest: Optional[bool] = None
    stale: Optional[bool] = None


@dataclass
class CompactSearchResult(Model):
    obs_id: str
    session_id: str
    title: str
    type: ObservationType
    score: float
    timestamp: str


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
