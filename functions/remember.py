import dataclasses
from dataclasses import dataclass
from logger import get_logger
from datetime import datetime, timezone
from typing import List, Optional
from schema import CompressedObservation, Memory, MemoryType, Model
from state.kv import StateKV
from iii import IIIClient

from state.schema import KV, generate_id, jaccard_similarity

logger = get_logger("remember")


@dataclass(frozen=True)
class RememberPayload(Model):
    content: str
    type: Optional[str] = None
    concepts: Optional[List[str]] = None
    files: Optional[List[str]] = None


@dataclass(frozen=True)
class ForgetPayload(Model):
    session_id: Optional[str] = None
    observation_ids: Optional[List[str]] = None
    memory_id: Optional[str] = None


def register_remember_function(sdk: IIIClient, kv: StateKV):
    async def handle_remember(raw_data: dict):
        logger.info("handle_remember: %s", raw_data)  # fix: was print() debug statement
        data = RememberPayload.from_dict(raw_data)

        if (not data.content or not isinstance(data.content, str) or not data.content.strip()):
            return {"success": False, "error": "content is required"}

        if (data.files is not None and not isinstance(data.files, list)):
            return {"success": False, "error": "files must be an array"}

        if (data.concepts is not None and not isinstance(data.concepts, list)):
            return {"success": False, "error": "concepts must be an array"}

       
        valid_types = [m.value for m in MemoryType]

        mem_type = MemoryType(data.type) if data.type in valid_types else MemoryType.PATTERN

        now = datetime.now(timezone.utc).isoformat()

        existing_memories = await kv.list(KV.memories, Memory)
        superseded_id: Optional[str] = None
        lower_content = data.content.lower()

        for existing in existing_memories:
            if not existing.is_latest:
                continue

            similarity = jaccard_similarity(
                lower_content,
                existing.content.lower()
            )

            if similarity > 0.7:
                updated = dataclasses.replace(existing, is_latest=False)
                await kv.set(KV.memories, existing.id, updated)
                superseded_id = existing.id
                break

        memory: Memory = Memory(
            id=generate_id("mem"),
            created_at=now,
            updated_at=now,
            type=mem_type,
            title=data.content[:80],
            content=data.content,
            concepts=data.concepts or [],
            files=data.files or [], 
            session_ids=[],
            strength=7,
            version=2 if superseded_id is not None else 1,
            parent_id=superseded_id,
            supersedes=[superseded_id] if superseded_id is not None else [],
            is_latest=True
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
                await kv.delete(KV.observations(data.session_id), obs.id)  # fix: obs is a CompressedObservation dataclass, not a dict

            await kv.delete(KV.sessions, data.session_id)
            await kv.delete(KV.summaries, data.session_id)
            deleted += 2

        logger.info("Memory forgotten: %s", deleted)
        return {"success": True, "deleted": deleted}

    sdk.register_function({
        "id": "mem::forget"
    }, handle_forget)

    sdk.register_function({
        "id": "mem::remember",
    }, handle_remember)
