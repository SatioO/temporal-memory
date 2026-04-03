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

        results: list[FileHistory] = []

        sessions = await kv.list(KV.sessions, Session)

        other_sessions = sorted([s for s in sessions if s.id != data.session_id],
                                key=lambda d: d.started_at, reverse=True)[:15]

        logger.info("data_files: %s", data)
        for file in data.files:
            history = FileHistory(file=file, observations=[])

            normalized_file = re.sub(r"^\./", "", file)

            for session in other_sessions:
                observations = await kv.list(KV.observations(
                    session.id), CompressedObservation)

                for obs in observations:
                    if not (obs.files or obs.title):
                        continue

                    matches = any(
                        f == file
                        or f == normalized_file
                        or f.endswith(f"/{normalized_file}")
                        or normalized_file.endswith(f"/{f}")
                        for f in obs.files
                    )

                    if matches and obs.importance >= 4:
                        history.observations.append(Observation(
                            session_id=session.id,
                            obs_id=obs.id,
                            type=obs.type,
                            title=obs.title,
                            narrative=obs.narrative,
                            importance=obs.importance,
                            timestamp=obs.timestamp,
                        ))

            history.observations.sort(
                key=lambda x: x.importance, reverse=True)
            history.observations = history.observations[:5]

            if len(history.observations) > 0:
                results.append(history)

        if len(results) == 0:
            return {"context": ""}

        lines = ["<agentmemory-file-context>"]

        for fh in results:
            lines.append(f"## {fh.file}")
            for obs in fh.observations:
                lines.append(f"- [{obs.type}] {obs.title}: {obs.narrative}")

        lines.append("</agentmemory-file-context>")

        context = "\n".join(lines)

        logger.info(
            "File context generated (files: %s, results: %s)",
            len(data.files),
            len(results)
        )

        return {"context": context}

    sdk.register_function(
        {"id": "mem::file_context"},
        handle_file_context
    )
