import asyncio
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set
from iii import IIIClient
from logger import get_logger

from schema import CompressedObservation, Memory, MemoryProvider, Model, Session
from state.kv import StateKV
from state.schema import KV, generate_id

logger = get_logger("consolidate")

CONSOLIDATION_SYSTEM = json.dumps({
    "instruction": (
        "You are a memory consolidation engine. Given a set of related observations "
        "from coding sessions, synthesize them into a single long-term memory."
    ),
    "output_format": "json_only",
    "rules": [
        "Return ONLY valid JSON. Do not include explanations or extra text.",
        "title must be concise (max 80 characters)",
        "content must be 2-4 sentences describing the learned insight",
        "type must be one of: pattern, preference, architecture, bug, workflow, fact",
        "concepts must contain key terms extracted from observations",
        "files must include relevant file paths",
        "strength must be an integer between 1 and 10"
    ],
    "schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "pattern",
                    "preference",
                    "architecture",
                    "bug",
                    "workflow",
                    "fact"
                ],
                "description": "Category of the memory"
            },
            "title": {
                "type": "string",
                "description": "Concise memory title (max 80 characters)"
            },
            "content": {
                "type": "string",
                "description": "2-4 sentence description of the learned insight"
            },
            "concepts": {
                "type": "array",
                "description": "Key terms or concepts extracted from observations",
                "items": {
                    "type": "string",
                    "description": "Single concept keyword"
                }
            },
            "files": {
                "type": "array",
                "description": "Relevant file paths associated with the memory",
                "items": {
                    "type": "string",
                    "description": "File path"
                }
            },
            "strength": {
                "type": "number",
                "description": "Confidence/importance score from 1 to 10"
            }
        },
        "required": [
            "type",
            "title",
            "content",
            "concepts",
            "files",
            "strength"
        ]
    }
})


@dataclass
class ConsolidatePayload(Model):
    project: Optional[str] = None
    min_obs: Optional[int] = 10


def register_consolidate_function(sdk: IIIClient, kv: StateKV, provider: MemoryProvider):
    async def handle_consolidate(raw_data: dict):
        data = ConsolidatePayload.from_dict(raw_data)
        min_obs = data.min_obs

        sessions = await kv.list(KV.memories, Session)
        filtered = [s for s in sessions if s.project ==
                    data.project] if data.project is not None else sessions

        all_obs: List[Dict[str, Any]] = []

        for session in filtered:
            observations = await kv.list(KV.observations(session.id), CompressedObservation)

            for obs in observations:
                if obs.title and obs.importance >= 5:
                    all_obs.append({
                        **obs.to_dict(),
                        "sid": session.id,
                    })

        if len(all_obs) < min_obs:
            return {"consolidated": 0, "reason": "insufficient_observations"}

        concept_groups = defaultdict(list)
        for obs in all_obs:
            for concept in obs["concepts"]:
                key = concept.lower()

                concept_groups[key].append(obs)

        consolidated = 0
        existing_memories = await kv.list(KV.memories, Memory)
        existing_titles = [m.title.lower() for m in existing_memories]

        for concept, obs_group in concept_groups.items():
            if len(obs_group) < 3:
                continue

            top = sorted(
                obs_group, key=lambda x: x["importance"], reverse=True)[:8]

            session_ids = list({o["sid"] for o in top})
            prompt = "\n\n".join(
                f"[{o['type']}] {o['title']}\n"
                f"{o.get('narrative', '')}\n"
                f"Files: {', '.join(o.get('files', []))}\n"
                f"Importance: {o['importance']}"
                for o in top
            )
            try:
                response = await asyncio.wait_for(
                    provider.compress(
                        CONSOLIDATION_SYSTEM,
                        f'Concept: "{concept}"\n\nObservations:\n{prompt}',
                    ),
                    timeout=30,
                )

                parsed = json.loads(response)
                if not parsed:
                    continue

                existing_match = next(
                    (
                        m
                        for m in existing_memories
                        if m.title.lower() == parsed["title"].lower()
                    ),
                    None,
                )
                now = datetime.utcnow().isoformat()

                if existing_match:
                    # mark existing as not latest (immutable-safe)
                    updated_old = replace(existing_match, is_latest=False)
                    await kv.set(KV.memories, updated_old.id, updated_old)

                    evolved = {
                        "id": generate_id("mem"),
                        "created_at": now,
                        "updated_at": now,
                        **parsed,
                        "version": (existing_match.version or 1) + 1,
                        "parent_id": existing_match.id,
                        "supersedes": [
                            existing_match.id,
                            *(existing_match.supersedes or []),
                        ],
                        "is_latest": True,
                    }

                    await kv.set(KV.memories, evolved["id"], evolved)
                    existing_titles.add(evolved["title"].lower())
                    consolidated += 1

                else:
                    memory = {
                        "id": generate_id("mem"),
                        "created_at": now,
                        "updated_at": now,
                        **parsed,
                        "version": 1,
                        "is_latest": True,
                    }

                    await kv.set(KV.memories, memory["id"], memory)
                    existing_titles.add(memory["title"].lower())
                    consolidated += 1
            except Exception as err:
                logger.warning(
                    "Consolidation failed for concept (concept: %s, error: %s)", concept, err)

        logger.info("consolidation successful (total_obs: %s, consolidated: %s)", len(
            all_obs), consolidated)

        return {"consolidated": consolidated, "total_observations": len(all_obs)}

    sdk.register_function(
        {"id": "mem:consolidate"},
        handle_consolidate
    )
