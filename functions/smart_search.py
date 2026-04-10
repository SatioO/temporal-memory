import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional
from iii import IIIClient
from logger import get_logger

from schema import CompactSearchResult, CompressedObservation, HybridSearchResult, Model, Session
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

        if data.expand_ids is not None and len(data.expand_ids) > 0:
            async def find_and_wrap(obs_id: str) -> Optional[dict]:
                obs = await _find_observation(kv, obs_id)
                if obs is None:
                    return None
                return {"obs_id": obs_id, "session_id": obs.session_id, "observation": obs}

            # fetch all expand_ids concurrently instead of sequentially
            results = await asyncio.gather(*[find_and_wrap(oid) for oid in data.expand_ids])
            expanded = [r for r in results if r is not None]

            logger.info("Smart search expanded: requested: %s, found: %s",
                        len(data.expand_ids), len(expanded))

            return {"mode": "expanded", "results": expanded}

        if data.query is None:
            return {"mode": "compact", "results": [], "error": "query is required"}

        hybrid_results = await search_fn(data.query, data.limit)

        compact = [
            CompactSearchResult(
                obs_id=result.observation.id,
                session_id=result.session_id,
                title=result.observation.title,
                score=result.combined_score,
                timestamp=result.observation.timestamp,
            ) for result in hybrid_results
        ]

        logger.info("Smart search compact: query: %s, results: %s",
                    data.query, len(compact))
        return {"mode": "compact", "results": compact}

    sdk.register_function({
        "id": "mem::smart_search",
        "description": "Search with progressive disclosure: compact results first, expand specific IDs for full details"
    }, handle_smart_search)


async def _find_observation(
    stateKv: StateKV,
    obs_id: str,
) -> Optional[CompressedObservation]:
    sessions = await stateKv.list(KV.sessions, Session)

    async def try_session(session: Session) -> Optional[CompressedObservation]:
        try:
            return await stateKv.get(KV.observations(session.id), obs_id, CompressedObservation)
        except Exception:
            return None

    results = await asyncio.gather(*[try_session(s) for s in sessions])
    return next((r for r in results if r is not None), None)
