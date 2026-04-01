import asyncio
from math import ceil
from state.schema import KV
from state.kv import StateKV
from schema.base import Model
from schema import ContextBlock, Session, SessionSummary, CompressedObservation
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from iii import IIIClient
from logger import get_logger

logger = get_logger("context")


def estimate_tokens(content: str) -> int:
    return ceil(len(content) / 3)


def escape_xml_attr(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace('"', "&quot;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


@dataclass(frozen=True)
class ContextHandlerParams(Model):
    session_id: str
    project: str
    budget: Optional[int] = None


def register_context_function(sdk: IIIClient, kv: StateKV, token_budget: int) -> None:
    async def handle_context(raw_data: dict):
        data = ContextHandlerParams.from_dict(raw_data)

        budget = data.budget if data.budget is not None else token_budget
        blocks: List[ContextBlock] = []

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

        async def safe_get_summaries(session_id):
            try:
                return await kv.get(KV.summaries, session_id)
            except Exception as e:
                logger.warning("Failed to fetch summary", {
                    "session_id": session_id, "error": str(e)})
                return None

        summaries_per_session = await asyncio.gather(
            *[safe_get_summaries(s.id) for s in sessions]
        )

        sessions_needing_obs = []

        for idx in range(len(sessions)):
            raw_summary = summaries_per_session[idx]
            summary = SessionSummary.from_dict(
                raw_summary) if raw_summary else None
            if summary:
                content = (
                    f"## {summary.title}\n"
                    f"{summary.narrative}\n"
                    f"Decisions: {'; '.join(summary.key_decisions)}\n"
                    f"Files: {', '.join(summary.files_modified)}"
                )
                blocks.append(ContextBlock(
                    type="summary",
                    content=content,
                    tokens=estimate_tokens(content),
                    recency=int(
                        datetime.fromisoformat(
                            summary.created_at.replace("Z", "+00:00"))
                        .timestamp() * 1000
                    ))
                )
            else:
                sessions_needing_obs.append(idx)

        print(f"session_needs_observation: {len(sessions_needing_obs)}")

        async def safe_get_observations(session_id):
            try:
                return await kv.list(KV.observations(session_id))
            except Exception as e:
                logger.warning("Failed to fetch summary", {
                    "session_id": session_id, "error": str(e)})
                return None

        observations_per_session = await asyncio.gather(
            *[safe_get_observations(sessions[i].id) for i in sessions_needing_obs]
        )

        for jdx in range(len(sessions_needing_obs)):
            i = sessions_needing_obs[jdx]
            raw_observations = observations_per_session[jdx] or []
            observations = [CompressedObservation.from_dict(
                o) for o in raw_observations]
            print(f"observations: {observations}")
            important = [
                o for o in observations if o.title and o.importance >= 5]
            print(f"important: {important}")
            if len(important) > 0:
                items = "\n".join(
                    f"- [{o.type}] {o.title}: {o.narrative}"
                    for o in sorted(important, key=lambda x: x.importance, reverse=True)[:5]
                )
                content = (
                    f"## Session {sessions[i].id[-8:]} (started at {sessions[i].started_at})\n"
                    f"{items}"
                )
                blocks.append(ContextBlock(
                    type="observation",
                    content=content,
                    tokens=estimate_tokens(content),
                    recency=int(
                        datetime.fromisoformat(
                            sessions[i].started_at.replace("Z", "+00:00"))
                        .timestamp() * 1000
                    ))
                )

        sorted_blocks = sorted(
            blocks, key=lambda x: x.recency, reverse=True)
        print(f"sorted_blocks: {sorted_blocks}")

        used_tokens = 0
        selected_blocks = []

        header = f'<graphmind-context project="{escape_xml_attr(data.project)}">'
        footer = "</graphmind-context>"
        used_tokens += estimate_tokens(header) + estimate_tokens(footer)

        for block in sorted_blocks:
            if used_tokens + block.tokens > budget:
                break
            selected_blocks.append(block.content)
            used_tokens += block.tokens

        print(f"selected_blocks: {selected_blocks}")

        if len(selected_blocks) == 0:
            logger.warning(
                "no_context_available (project=%s)", data.project)
            return {"success": True, "context": "", "blocks": 0, "tokens": 0}

        blocks_text = "\n\n".join(selected_blocks)
        result = f"{header}\n{blocks_text}\n{footer}"
        logger.info("context_generated (blocks=%s, tokens=%s)",
                    len(selected_blocks), used_tokens)

        return {"context": result, "blocks": len(selected_blocks), "tokens": used_tokens}

    sdk.register_function({"id": "mem::context"}, handle_context)
