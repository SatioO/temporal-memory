import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional
from iii import IIIClient
from logger import get_logger
from schema import CompactSearchResult, CompressedObservation, HybridSearchResult, Model, Session
from state.kv import StateKV
from state.schema import KV

logger = get_logger("smart_search")

_EXPAND_CAP = 20
_MAX_LIMIT = 100


@dataclass(frozen=True)
class SmartSearchPayload(Model):
    query: Optional[str] = None
    expand_ids: Optional[List[Any]] = None
    limit: Optional[int] = None


def register_smart_search_fn(
    sdk: IIIClient,
    kv: StateKV,
    search_fn: Callable[[str, int], Awaitable[List[HybridSearchResult]]],
):
    async def handle_smart_search(raw_data: dict):
        # --- expand mode ---
        raw_expand = raw_data.get("expand_ids") or raw_data.get("expandIds")
        if raw_expand and isinstance(raw_expand, list) and len(raw_expand) > 0:
            truncated = len(raw_expand) > _EXPAND_CAP
            items_raw = raw_expand[:_EXPAND_CAP]

            # accept both plain strings and {obs_id/obsId, session_id/sessionId} dicts
            items: List[dict] = []
            for entry in items_raw:
                if isinstance(entry, str):
                    items.append({"obs_id": entry, "session_id": None})
                elif isinstance(entry, dict):
                    obs_id = entry.get("obs_id") or entry.get("obsId")
                    session_id = entry.get(
                        "session_id") or entry.get("sessionId")
                    if isinstance(obs_id, str):
                        items.append(
                            {"obs_id": obs_id, "session_id": session_id})

            async def find_and_wrap(obs_id: str, session_id: Optional[str]) -> Optional[dict]:
                obs = await _find_observation(kv, obs_id, session_id)
                if obs is None:
                    return None
                return {"obs_id": obs_id, "session_id": obs.session_id, "observation": obs.to_dict()}

            results = await asyncio.gather(
                *[find_and_wrap(it["obs_id"], it["session_id"]) for it in items]
            )
            expanded = [r for r in results if r is not None]

            logger.info(
                "smart search expanded: requested=%s, attempted=%s, returned=%s, truncated=%s",
                len(raw_expand), len(items), len(expanded), truncated,
            )
            return {"mode": "expanded", "results": expanded, "truncated": truncated}

        # --- compact mode ---
        query = raw_data.get("query")
        if not isinstance(query, str) or not query.strip():
            return {"mode": "compact", "results": [], "error": "query is required"}
        query = query.strip()

        raw_limit = raw_data.get("limit")
        limit = max(1, min(raw_limit if isinstance(
            raw_limit, int) else 20, _MAX_LIMIT))

        hybrid_results = await search_fn(query, limit)

        compact = [
            CompactSearchResult(
                obs_id=r.observation.id,
                session_id=r.session_id,
                title=r.observation.title,
                type=r.observation.type,
                score=r.combined_score,
                timestamp=r.observation.timestamp,
            ).to_dict()
            for r in hybrid_results
        ]

        logger.info("smart search compact: query=%s, results=%s",
                    query, len(compact))
        return {"mode": "compact", "results": compact}

    sdk.register_function({
        "id": "mem::smart-search",
        "description": "Search with progressive disclosure: compact results first, expand specific IDs for full details",
    }, handle_smart_search)


async def _find_observation(
    kv: StateKV,
    obs_id: str,
    session_id_hint: Optional[str] = None,
) -> Optional[CompressedObservation]:
    # Fast path: try the hinted session first
    if session_id_hint:
        try:
            obs = await kv.get(KV.observations(session_id_hint), obs_id, CompressedObservation)
            if obs is not None:
                return obs
        except Exception:
            pass

    # Fallback: batched scan with early exit (5 sessions at a time)
    sessions = await kv.list(KV.sessions, Session)
    for i in range(0, len(sessions), 5):
        batch = sessions[i:i + 5]
        results = await asyncio.gather(
            *[_try_get(kv, s.id, obs_id) for s in batch]
        )
        found = next((r for r in results if r is not None), None)
        if found:
            return found

    return None


async def _try_get(kv: StateKV, session_id: str, obs_id: str) -> Optional[CompressedObservation]:
    try:
        return await kv.get(KV.observations(session_id), obs_id, CompressedObservation)
    except Exception:
        return None
