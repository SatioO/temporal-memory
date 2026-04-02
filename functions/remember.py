from dataclasses import dataclass
from logger import get_logger
from datetime import datetime, timezone
from typing import List, Optional
from schema import CompressedObservation, Memory, Model
from state.kv import StateKV
from iii import IIIClient

from state.schema import KV, generate_id

logger = get_logger("remember")


@dataclass(frozen=True)
class RememberPayload(Model):
    content: str
    type: Optional[str]
    concepts: Optional[List[str]]
    files: Optional[List[str]]
    ttl_days: Optional[int]
    source_ob_ids: Optional[List[str]]


@dataclass(frozen=True)
class ForgetPayload(Model):
    session_id: Optional[str]
    observation_ids: Optional[List[str]]
    memory_id: Optional[str]


def register_remember_function(sdk: IIIClient, kv: StateKV):
    async def handle_remember(raw_data: dict):
        data = RememberPayload.from_dict(raw_data)

        if (not data.content or not isinstance(data.content, str) or not data.content.strip()):
            return {"success": False, "error": "content is required"}

        if (data.files is not None and not isinstance(data.files, list)):
            return {"success": False, "error": "files must be an array"}

        if (data.concepts is not None and not isinstance(data.concepts, list)):
            return {"success": False, "error": "concepts must be an array"}

        if (data.source_ob_ids is not None and not isinstance(data.source_ob_ids, list)):
            return {"success": False, "error": "source_ob_ids must be an array"}

        valid_types = [
            "pattern",
            "preference",
            "architecture",
            "bug",
            "workflow",
            "fact"
        ]

        mem_type = data.type if data.type in valid_types else "fact"

        now = datetime.now(timezone.utc).isoformat()
        # TODO: need existing memory checks, strength metric calculation

        memory: Memory = Memory(
            id=generate_id("mem"),
            created_at=now,
            updated_at=now,
            type=mem_type,
            title=data.content[:80],
            content=data.content,
            concepts=data.concepts,
            files=data.files,
            session_ids=[],
            strength=7
        )

        await kv.set(KV.memories, memory.id, memory)

        logger.info("Memory saved (id: %s, type: %s)", memory.id, memory.type)
        return {"success": True, "memory": memory}

    async def handle_forget(raw_data: dict):
        data = ForgetPayload.from_dict(raw_data)

        deleted: int = 0

        if data.memory_id:
            await kv.delete(KV.memories, data.memory_id)
            deleted += 1

        if data.observation_ids and len(data.observation_ids) > 0 and data.session_id:
            for ob_id in data.observation_ids:
                await kv.delete(KV.observations(data.session_id), ob_id)
                deleted += 1

        if not data.observation_ids and data.session_id:
            observations = await kv.list(KV.observations(data.session_id), CompressedObservation)

            for obs in observations:
                await kv.delete(KV.observations(data.session_id), obs.get("id"))

            await kv.delete(KV.sessions, data.session_id)
            await kv.delete(KV.summaries, data.session_id)
            deleted += 2

        logger.info("Memory forgotten: %s", deleted)
        return {"success": True, "deleted": deleted}

    sdk.register_function({
        "id": "mem::remember"
    }, handle_remember)

    sdk.register_function({
        "id": "mem::forget"
    }, handle_forget)
