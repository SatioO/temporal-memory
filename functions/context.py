from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from iii import IIIClient

from schema import ContextBlock, ProjectProfile, Session
from state.kv import StateKV
from state.schema import KV


@dataclass
class ContextResponse:
    context: str


@dataclass
class ContextHandlerParams:
    session_id: str
    project: str
    budget: Optional[int] = None


def register_context_function(sdk: IIIClient, kv: StateKV, token_budget: int) -> None:
    async def handle_context(data: ContextHandlerParams):
        budget = data.budget if data.budget is not None else token_budget
        blocks: List[ContextBlock] = []
        print(f"recieved: {data}")

        profile: ProjectProfile = await kv.get(KV.profiles, data.project)
        if profile is not None:
            print(f"[graphmind] found profile: {profile}")

        # TODO: This needs more rethinking as it is getting all the sessions from cache than getting project specific sessions
        raw_sessions = await kv.list(KV.sessions)
        all_sessions: List[Session] = [Session.model_validate(s) for s in raw_sessions] if raw_sessions else []
        print(f"[graphmind] found sessions: {all_sessions}")

        sessions = sorted(
            [
                s for s in all_sessions
                if s.project == data.project and s.id != data.session_id
            ],
            key=lambda s: datetime.fromisoformat(s.started_at),
            reverse=True
        )[:10]

        print(f"[graphmind] filtered sessions: {sessions}")

        return ContextResponse(context="12345")

    sdk.register_function({"id": "mem::context"}, handle_context)
