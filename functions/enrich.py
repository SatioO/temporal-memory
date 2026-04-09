import asyncio
import json
from dataclasses import dataclass
from typing import Any, List, Optional

from iii import IIIClient, TriggerRequest
from logger import get_logger
from functions.file_context import FileContextPayload
from schema import Memory, Model
from state.kv import StateKV
from state.schema import KV, parse_ts

logger = get_logger("enrich")

MAX_CONTEXT_LENGTH = 4000


@dataclass
class EnrichPayload(Model):
    session_id: str
    files: List[str]
    terms: Optional[List[str]] = None
    tool_name: Optional[str] = None


def register_enrich_function(sdk: IIIClient, kv: StateKV):
    async def handle_enrich(raw_data: dict):
        data = EnrichPayload.from_dict(raw_data)

        search_queries = list(dict.fromkeys(
            [
                *(f.split("/")[-1] or f for f in data.files),
                *(data.terms or []),
            ]
        ))
        search_queries = [q for q in search_queries if q]

        async def fetch_file_context():
            try:
                return await sdk.trigger_async(TriggerRequest(
                    function_id="mem::file_context",
                    payload=FileContextPayload(
                        data.session_id, data.files).to_dict(),
                ))
            except Exception:
                return {"context": ""}

        async def fetch_search():
            if not search_queries:
                return []
            try:
                return await sdk.trigger_async(TriggerRequest(
                    function_id="mem::search",
                    payload={"query": " ".join(search_queries), "limit": 5},
                ))
            except Exception:
                return []

        async def fetch_memories():
            try:
                return await kv.list(KV.memories, Memory)
            except Exception:
                return []

        file_context, search_result, memories = await asyncio.gather(
            fetch_file_context(),
            fetch_search(),
            fetch_memories(),
        )

        bug_memories = [
            m
            for m in memories
            if (
                m.type == "bug"
                and m.is_latest
                and any(
                    (f in df) or (df in f)
                    for f in m.files
                    for df in data.files
                )
            )
        ]

        bug_memories.sort(
            key=lambda m: parse_ts(m.updated_at or m.created_at),
            reverse=True,
        )

        parts: List[Any] = []

        # file context
        if file_context.get("context"):
            parts.append(file_context["context"])

        results_list = search_result if isinstance(
            search_result, list) else search_result.get("results", [])
        if results_list:
            observations = [
                r.get("observation", {}).get("narrative")
                for r in results_list
                if r.get("observation") and r["observation"].get("narrative")
            ]
            if observations:
                parts.append({"agentmemory_relevant_context": observations})

        if bug_memories:
            parts.append({
                "agentmemory_past_errors": [
                    {"title": m.title, "content": m.content}
                    for m in bug_memories[:3]
                ]
            })

        context_obj = {"parts": parts}
        context = json.dumps(context_obj)

        truncated = False
        if len(context) > MAX_CONTEXT_LENGTH:
            while parts and len(json.dumps({"parts": parts})) > MAX_CONTEXT_LENGTH:
                parts.pop()
            context = json.dumps({"parts": parts})
            truncated = True

        logger.info(
            "Enrichment completed | session_id=%s file_count=%s context_length=%s truncated=%s",
            data.session_id,
            len(data.files),
            len(context),
            truncated,
        )

        return {"context": context, "truncated": truncated}

    sdk.register_function(
        {"id": "mem::enrich", "description": "Aggregate file context, relevant observations, and bug memories for pre-tool enrichment"},
        handle_enrich
    )
