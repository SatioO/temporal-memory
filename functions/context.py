from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from iii import IIIClient
from logger import get_logger

logger = get_logger("context")

from schema import ContextBlock, ProjectProfile, Session
from schema.base import Model
from state.kv import StateKV
from state.schema import KV


@dataclass(frozen=True)
class ContextResult(Model):
    context: str


@dataclass(frozen=True)
class ContextHandlerParams(Model):
    session_id: str
    project: str
    budget: Optional[int] = None


def register_context_function(sdk: IIIClient, kv: StateKV, token_budget: int) -> None:
    async def handle_context(data_raw: dict):
        data = ContextHandlerParams.from_dict(data_raw)

        budget = data.budget if data.budget is not None else token_budget
        blocks: List[ContextBlock] = []
        logger.debug("handle_context received: %s", data)

        profile: ProjectProfile = await kv.get(KV.profiles, data.project)
        if profile is not None:
            logger.debug("found profile: %s", profile)

        # TODO: This needs more rethinking — currently gets all sessions, not project-specific
        raw_sessions = await kv.list(KV.sessions)
        all_sessions: List[Session] = [Session.from_dict(
            s) for s in raw_sessions] if raw_sessions else []

        sessions = sorted(
            [
                s for s in all_sessions
                if s.project == data.project and s.id != data.session_id
            ],
            key=lambda s: datetime.fromisoformat(s.started_at),
            reverse=True,
        )[:10]

        # TODO: Pending impl
        return ContextResult(context="[TODO]: context not implemented").to_dict()

    sdk.register_function({"id": "mem::context"}, handle_context)
