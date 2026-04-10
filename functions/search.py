import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
from iii.types import IIIClient
from logger import get_logger
from query.bm25_index import get_bm25_index
from schema import CompressedObservation, Model, Session
from state.kv import StateKV
from state.schema import KV


logger = get_logger("search")

MAX_LIMIT = 100


@dataclass(frozen=True)
class SearchPayload(Model):
    query: str
    limit: Optional[int] = None
    project: Optional[str] = None
    cwd: Optional[str] = None


async def rebuild_index(kv: StateKV) -> int:
    idx = get_bm25_index()
    idx.clear()

    sessions = await kv.list(KV.sessions, Session)
    if not sessions:
        return 0

    count = 0
    failed_sessions: List[str] = []

    for batch_start in range(0, len(sessions), 10):
        chunk = sessions[batch_start:batch_start + 10]

        async def load_session_obs(s: Session) -> List[CompressedObservation]:
            try:
                return await kv.list(KV.observations(s.id), CompressedObservation)
            except Exception:
                failed_sessions.append(s.id)
                return []

        results = await asyncio.gather(*[load_session_obs(s) for s in chunk])

        for observations in results:
            for obs in observations:
                if obs.title and obs.narrative:
                    idx.add(obs)
                    count += 1

    if failed_sessions:
        logger.warning("rebuild_index: failed to load observations for sessions: %s", failed_sessions)

    return count


def register_search_function(sdk: IIIClient, kv: StateKV):
    async def handle_search(raw_data: dict):
        # Input validation
        query = raw_data.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("mem::search: query must be a non-empty string")
        query = query.strip()

        raw_limit = raw_data.get("limit")
        if raw_limit is not None:
            if not isinstance(raw_limit, int) or raw_limit < 1:
                raise ValueError("mem::search: limit must be a positive integer")
            effective_limit = min(raw_limit, MAX_LIMIT)
        else:
            effective_limit = 20

        project_filter = raw_data.get("project") or None
        cwd_filter = raw_data.get("cwd") or None
        if isinstance(project_filter, str) and not project_filter:
            project_filter = None
        if isinstance(cwd_filter, str) and not cwd_filter:
            cwd_filter = None

        idx = get_bm25_index()

        if idx.size() == 0:
            count = await rebuild_index(kv)
            logger.info("search index rebuilt", {"entries": count})

        filtering = bool(project_filter or cwd_filter)
        fetch_limit = max(effective_limit * 10, 100) if filtering else effective_limit
        results = idx.search(query, fetch_limit)

        # Resolve session -> project/cwd with a per-call cache
        session_cache: Dict[str, Optional[Session]] = {}

        async def load_session(session_id: str) -> Optional[Session]:
            if session_id in session_cache:
                return session_cache[session_id]
            s = await kv.get(KV.sessions, session_id, Session)
            session_cache[session_id] = s
            return s

        # Filter pass (sequential to benefit from session cache)
        candidates = []
        for r in results:
            if len(candidates) >= effective_limit:
                break
            if filtering:
                s = await load_session(r["session_id"])
                if not s:
                    continue
                if project_filter and s.project != project_filter:
                    continue
                if cwd_filter and s.cwd != cwd_filter:
                    continue
            candidates.append(r)

        # Parallel observation fetch
        observations = await asyncio.gather(
            *[kv.get(KV.observations(r["session_id"]), r["obs_id"], CompressedObservation) for r in candidates],
            return_exceptions=True,
        )

        enriched = []
        for i, obs in enumerate(observations):
            if isinstance(obs, CompressedObservation):
                enriched.append({
                    "observation": obs.to_dict(),
                    "score": candidates[i]["score"],
                    "session_id": candidates[i]["session_id"],
                })

        logger.info("search completed", {
            "query": query,
            "results": len(enriched),
            "has_project_filter": bool(project_filter),
            "has_cwd_filter": bool(cwd_filter),
        })
        return {"results": enriched}

    sdk.register_function({
        "id": "mem::search",
        "description": "Search observations by keyword",
    }, handle_search)
