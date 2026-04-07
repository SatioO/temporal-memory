from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional
from iii import IIIClient
from logger import get_logger

from schema import CompressedObservation, HybridSearchResult, Model, Session
from state.kv import StateKV
from state.schema import KV
logger = get_logger("smart_search")


@dataclass
class SmartSearchPayload(Model):
    query: Optional[str] = None
    expand_ids: Optional[List[str]] = None
    limit: Optional[int] = 20


def register_smart_search_fn(sdk: IIIClient, kv: StateKV, search_fn: Callable[[str, int], Awaitable[List[HybridSearchResult]]]):
    async def handle_smart_search(raw_data: dict):
        data = SmartSearchPayload.from_dict(raw_data)

        if data.expand_ids != None and len(data.expand_ids) > 0:
            expanded = []

            for obs_id in data.expand_ids:
                obs = _find_observation(obs_id)
                if obs != None:
                    expanded.append({
                        "obs_id": obs_id,
                        "session_id": obs.sessionId,
                        "observation": obs,
                    })

            logger.info("Smart search expanded: requested: %s, found: %s",
                        len(data.expand_ids), expanded.length)

            return {"mode": "expanded", "results": expanded}

        if data.query is None:
            return {"mode": "compact", "results": [], "error": "query is required"}

        hybrid_results = await search_fn(data.query, data.limit)

        compact = [
            HybridSearchResult(
                obs_id=result.observation.id,
                session_id=result.session_id,
                title=result.observation.title,
                type=result.observation.type,
                score=result.combined_score,
                timestamp=result.observation.timestamp
            ) for result in hybrid_results
        ]

        logger.info("Smart search compact: query: %s, results: %s",
                    data.query, compact.length)
        return {"mode": "compact", "results": compact}

    sdk.register_function({
        "id": "mem::smart_search",
        "description": "Search with progressive disclosure: compact results first, expand specific IDs for full details"
    }, handle_smart_search)


async def _find_observation(
    stateKv: StateKV,
    obs_id: str,
) -> Optional[CompressedObservation]:
    sessions = await stateKv.list(KV.observations(), Session)

    for session in sessions:
        try:
            obs = await stateKv.get(KV.observations(session.id), obs_id, CompressedObservation)
        except Exception:
            obs = None

        if obs is not None:
            return obs

    return None
