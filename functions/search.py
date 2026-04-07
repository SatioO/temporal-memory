import threading
from dataclasses import dataclass
from typing import List, Optional
from iii.types import IIIClient
from logger import get_logger
from schema import CompressedObservation, Model, SearchResult, Session
from state.kv import StateKV
from state.schema import KV
from state.search_index import SearchIndex

search_index: Optional[SearchIndex] = None
_lock = threading.Lock()

logger = get_logger("search")


def get_search_index() -> SearchIndex:
    global search_index

    if search_index is None:
        with _lock:
            search_index = SearchIndex()

    return search_index


@dataclass(frozen=True)
class SearchPayload(Model):
    query: str
    limit: Optional[int]


async def rebuild_index(kv: StateKV) -> int:
    idx = get_search_index()
    idx.clear()

    sessions = await kv.list(KV.sessions, Session)

    if len(sessions) == 0:
        return 0

    count = 0

    for session in sessions:
        observations = await kv.list(KV.observations(
            session.id), CompressedObservation)

        for obs in observations:
            if obs.title and obs.narrative:
                idx.add(obs)
                count += 1

    return count


def register_search_function(sdk: IIIClient, kv: StateKV):
    async def handle_search(raw_data: dict):
        data = SearchPayload.from_dict(raw_data)

        idx = get_search_index(kv)

        if idx.size == 0:
            count = await rebuild_index()
            logger.info("search index rebuilt: count: %s", count)

        results = idx.search(data.query, data.limit or 20)
        enriched: List[SearchResult] = []

        for r in results:
            ob = kv.get(KV.observations(r.session_id), r.obs_id)
            if (ob):
                enriched.append(
                    {"observation": ob, "score": r.score, "session_id": r.session_id})

        return enriched

    sdk.register_function({
        "id": "mem::search",
        "description": "search observations by keyword"
    }, handle_search)
