import asyncio
import re
from dataclasses import dataclass
from iii.types import IIIClient

from logger import get_logger
from schema import CompressedObservation, Model, Session, FileHistory
from state.kv import StateKV
from state.schema import KV

logger = get_logger("file_context")


@dataclass
class FileContextPayload(Model):
    session_id: str
    files: list[str]


@dataclass
class Observation(Model):
    session_id: str
    obs_id: str
    type: str
    title: str
    narrative: str
    importance: float
    timestamp: str


def register_file_context_function(sdk: IIIClient, kv: StateKV):
    async def handle_file_context(raw_data: FileContextPayload):
        data = FileContextPayload.from_dict(raw_data)

        sessions = await kv.list(KV.sessions, Session)
        other_sessions = sorted(
            [s for s in sessions if s.id != data.session_id],
            key=lambda s: s.started_at,
            reverse=True,
        )[:15]

        # Fetch all session observations in parallel
        all_obs_lists: list[list[CompressedObservation]] = await asyncio.gather(
            *[kv.list(KV.observations(s.id), CompressedObservation) for s in other_sessions]
        )

        # Build a flat list of (session_id, obs) for relevant observations only
        candidate_obs = [
            (session.id, obs)
            for session, obs_list in zip(other_sessions, all_obs_lists)
            for obs in obs_list
            if obs.files and obs.title and obs.importance >= 4
        ]

        results: list[FileHistory] = []

        for file in data.files:
            normalized_file = re.sub(r"^\./", "", file)
            history = FileHistory(file=file, observations=[])

            for session_id, obs in candidate_obs:
                matches = any(
                    f == file
                    or f == normalized_file
                    or f.endswith(f"/{normalized_file}")
                    or normalized_file.endswith(f"/{f}")
                    for f in obs.files
                )
                if matches:
                    history.observations.append(Observation(
                        session_id=session_id,
                        obs_id=obs.id,
                        type=obs.type,
                        title=obs.title,
                        narrative=obs.narrative,
                        importance=obs.importance,
                        timestamp=obs.timestamp,
                    ))

            history.observations.sort(key=lambda x: x.importance, reverse=True)
            history.observations = history.observations[:5]

            if history.observations:
                results.append(history)

        if not results:
            return {"context": ""}

        lines = ["# Agent File Context"]
        for fh in results:
            lines.append(f"## {fh.file}")
            for obs in fh.observations:
                lines.append(f"- [{obs.type}] {obs.title}: {obs.narrative}")

        context = "\n".join(lines)

        logger.info(
            "File context generated (files: %s, results: %s)",
            len(data.files),
            len(results),
        )

        return {"context": context}

    sdk.register_function(
        {"id": "mem::file_context"},
        handle_file_context
    )
