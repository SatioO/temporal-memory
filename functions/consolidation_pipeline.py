from state.schema import KV, generate_id
from state.kv import StateKV
from schema.domain import Memory, MemoryType, ProceduralMemory, SemanticMemory
from schema.config import ConsolidatePipelineConfig
from schema.base import Model
from schema import MemoryProvider, SessionSummary
from prompts.consolidation import (
    PROCEDURAL_EXTRACTION_SYSTEM,
    SEMANTIC_MERGE_SYSTEM,
    build_procedural_extraction_prompt,
    build_semantic_merge_prompt,
)
from logger import get_logger
from iii import IIIClient, TriggerRequest
import dataclasses
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T")

logger = get_logger("consolidation_pipeline")


def _fact_similarity(a: str, b: str) -> float:
    """Jaccard token-overlap similarity between two fact strings (0–1)."""
    toks_a = set(a.lower().split())
    toks_b = set(b.lower().split())
    if not toks_a or not toks_b:
        return 0.0
    return len(toks_a & toks_b) / len(toks_a | toks_b)


_FUZZY_MATCH_THRESHOLD = 0.65  # facts with overlap ≥ this are treated as duplicates


def apply_decay(items: List[T], decay_days: float) -> List[T]:
    """Return new instances with decayed strength for items not accessed recently.
    """
    if decay_days <= 0 or not math.isfinite(decay_days):
        return items

    now = datetime.now(timezone.utc).timestamp() * \
        1000  # ms, matches Date.now()
    result: List[T] = []

    for item in items:
        last_access = getattr(item, "last_accessed_at",
                              None) or item.updated_at
        days_since = (now - datetime.fromisoformat(last_access).timestamp()
                      * 1000) / (1000 * 60 * 60 * 24)

        if days_since > decay_days:
            decay_periods = math.floor(days_since / decay_days)
            new_strength = max(0.1, item.strength *
                               math.pow(0.9, decay_periods))
            result.append(dataclasses.replace(item, strength=new_strength))
        else:
            result.append(item)

    return result


@dataclasses.dataclass
class ConsolidatePipelinePayload(Model):
    tier: Optional[str] = None
    force: Optional[bool] = None
    project: Optional[str] = None


def register_consolidation_pipeline_function(
    sdk: IIIClient,
    kv: StateKV,
    provider: MemoryProvider,
    config: ConsolidatePipelineConfig,
):
    async def handle_consolidate_pipeline(raw_data: dict):
        data = ConsolidatePipelinePayload.from_dict(raw_data)

        if not data.force and not config.enabled:
            return {
                "success": False,
                "skipped": True,
                "reason": "CONSOLIDATION_ENABLED is not set to true",
            }

        tier = "all" if data.tier is None else data.tier
        results: Dict[str, Any] = {}

        # ── Semantic tier ──────────────────────────────────────────────────────
        if tier in ("all", "semantic"):
            summaries = await kv.list(KV.summaries, SessionSummary)

            existing_semantic = await kv.list(KV.semantic, SemanticMemory)

            if len(summaries) < 1:
                results["semantic"] = {
                    "skipped": True,
                    "reason": "fewer than 5 summaries",
                }
            else:
                recent_summaries = sorted(
                    summaries, key=lambda s: s.created_at, reverse=True
                )[:20]

                prompt = build_semantic_merge_prompt([
                    {
                        "title": s.title,
                        "narrative": s.narrative,
                        "decisions": s.key_decisions,
                        "files": s.files_modified,
                        "concepts": s.concepts,
                    }
                    for s in recent_summaries
                ])

                try:
                    response = await provider.summarize(SEMANTIC_MERGE_SYSTEM, prompt)

                    # prompt guarantees strict JSON: {"facts": [{"fact": "...", "confidence": 0.0}]}
                    parsed = json.loads(response)
                    facts = parsed.get("facts", [])

                    new_facts = 0
                    now = datetime.now(timezone.utc).isoformat()

                    for item in facts:
                        fact = str(item.get("fact", "")).strip()
                        if not fact:
                            continue

                        try:
                            confidence = float(item.get("confidence", 0.5))
                        except (ValueError, TypeError):
                            confidence = 0.5
                        if not (0.0 <= confidence <= 1.0):
                            confidence = 0.5

                        category = str(item.get("category", "")).strip() or None
                        scope = str(item.get("scope", "project")).strip()
                        if scope not in ("project", "universal"):
                            scope = "project"
                        retrieval_hint = str(item.get("retrieval_hint", "")).strip() or None

                        # Fuzzy dedup: exact match first, then token-overlap fallback
                        existing = next(
                            (s for s in existing_semantic
                             if s.fact.lower() == fact.lower()),
                            None,
                        )
                        if existing is None:
                            existing = next(
                                (s for s in existing_semantic
                                 if _fact_similarity(s.fact, fact) >= _FUZZY_MATCH_THRESHOLD),
                                None,
                            )

                        if existing:
                            updated = dataclasses.replace(
                                existing,
                                access_count=existing.access_count + 1,
                                last_accessed_at=now,
                                updated_at=now,
                                confidence=max(existing.confidence, confidence),
                                strength=min(1.0, existing.strength + 0.05),
                                # Prefer more specific metadata when reinforcing
                                category=category or existing.category,
                                scope=scope if scope != "project" else existing.scope,
                                retrieval_hint=retrieval_hint or existing.retrieval_hint,
                            )
                            await kv.set(KV.semantic, updated.id, updated)
                        else:
                            sem = SemanticMemory(
                                id=generate_id("sem"),
                                fact=fact,
                                confidence=confidence,
                                source_session_ids=[
                                    s.session_id for s in recent_summaries
                                ],
                                source_memory_ids=[],
                                access_count=1,
                                last_accessed_at=now,
                                strength=confidence,
                                created_at=now,
                                updated_at=now,
                                category=category,
                                scope=scope,
                                retrieval_hint=retrieval_hint,
                            )
                            await kv.set(KV.semantic, sem.id, sem)
                            new_facts += 1

                    results["semantic"] = {
                        "new_facts": new_facts,
                        "total_summaries": len(summaries),
                    }

                except json.JSONDecodeError as err:
                    logger.error(
                        "Semantic consolidation: invalid JSON response error=%s", err)
                    results["semantic"] = {"error": f"JSON parse error: {err}"}
                except Exception as err:
                    logger.error("Semantic consolidation failed error=%s", err)
                    results["semantic"] = {"error": str(err)}

        # ── Reflect tier ───────────────────────────────────────────────────────
        if tier in ("all", "reflect"):
            try:
                reflect_result = await sdk.trigger_async(TriggerRequest(
                    function_id="mem::reflect",
                    payload={
                        "max_clusters": 10,
                        "project": data.project,
                    },
                ))
                results["reflect"] = reflect_result
            except Exception as err:
                logger.warning("Reflect tier failed error=%s", err)
                results["reflect"] = {"error": str(err)}

        # ── Procedural tier ────────────────────────────────────────────────────
        if tier in ("all", "procedural"):
            memories = await kv.list(KV.memories, Memory)
            patterns: List[Dict[str, Any]] = [
                {
                    "content": m.content,
                    "frequency": len(m.session_ids) or 1,
                }
                for m in memories
                if m.is_latest and m.type == MemoryType.PATTERN
                and (len(m.session_ids) or 1) >= 2
            ]

            # Collect session ids from the contributing pattern memories
            pattern_session_ids: List[str] = list({
                sid
                for m in memories
                if m.is_latest and m.type == MemoryType.PATTERN
                and (len(m.session_ids) or 1) >= 2
                for sid in m.session_ids
            })

            if len(patterns) < 2:
                results["procedural"] = {
                    "skipped": True,
                    "reason": "fewer than 2 recurring patterns",
                }
            else:
                prompt = build_procedural_extraction_prompt(patterns)

                try:
                    response = await provider.summarize(
                        PROCEDURAL_EXTRACTION_SYSTEM, prompt
                    )

                    parsed = json.loads(response)
                    procedures = parsed.get("procedures", [])

                    now = datetime.now(timezone.utc).isoformat()
                    existing_procs = await kv.list(KV.procedural, ProceduralMemory)
                    new_procs = 0

                    for item in procedures:
                        name = str(item.get("name", "")).strip()
                        trigger = str(item.get("trigger", "")).strip()
                        steps = [str(s).strip() for s in item.get("steps", []) if str(s).strip()]

                        if not name or not trigger or not steps:
                            continue

                        try:
                            proc_confidence = float(item.get("confidence", 0.5))
                        except (ValueError, TypeError):
                            proc_confidence = 0.5
                        if not (0.0 <= proc_confidence <= 1.0):
                            proc_confidence = 0.5

                        preconditions = [str(s).strip() for s in item.get("preconditions", []) if str(s).strip()] or None
                        postconditions = [str(s).strip() for s in item.get("postconditions", []) if str(s).strip()] or None
                        failure_modes = [str(s).strip() for s in item.get("failure_modes", []) if str(s).strip()] or None

                        existing = next(
                            (p for p in existing_procs
                             if p.name.lower() == name.lower()),
                            None,
                        )

                        if existing:
                            # Merge session sources and reinforce strength
                            merged_sids = list(set(existing.source_session_ids) | set(pattern_session_ids))
                            updated = dataclasses.replace(
                                existing,
                                frequency=existing.frequency + 1,
                                updated_at=now,
                                strength=min(1.0, existing.strength + 0.1),
                                confidence=max(existing.confidence, proc_confidence),
                                source_session_ids=merged_sids,
                                # Prefer richer metadata from later extractions
                                preconditions=preconditions or existing.preconditions,
                                postconditions=postconditions or existing.postconditions,
                                failure_modes=failure_modes or existing.failure_modes,
                            )
                            await kv.set(KV.procedural, updated.id, updated)
                        else:
                            proc = ProceduralMemory(
                                id=generate_id("proc"),
                                name=name,
                                steps=steps,
                                trigger_condition=trigger,
                                frequency=1,
                                source_session_ids=pattern_session_ids,
                                strength=proc_confidence,
                                created_at=now,
                                updated_at=now,
                                confidence=proc_confidence,
                                preconditions=preconditions,
                                postconditions=postconditions,
                                failure_modes=failure_modes,
                            )
                            await kv.set(KV.procedural, proc.id, proc)
                            new_procs += 1

                    results["procedural"] = {
                        "new_procedures": new_procs,
                        "patterns_analyzed": len(patterns),
                    }

                except json.JSONDecodeError as err:
                    logger.error(
                        "Procedural extraction: invalid JSON response error=%s", err)
                    results["procedural"] = {
                        "error": f"JSON parse error: {err}"}
                except Exception as err:
                    logger.error("Procedural extraction failed error=%s", err)
                    results["procedural"] = {"error": str(err)}

        # ── Decay tier ─────────────────────────────────────────────────────────
        if tier in ("all", "decay"):
            semantic = await kv.list(KV.semantic, SemanticMemory)
            semantic = apply_decay(semantic, config.decay_days)
            for s in semantic:
                await kv.set(KV.semantic, s.id, s)

            procedural = await kv.list(KV.procedural, ProceduralMemory)
            procedural = apply_decay(procedural, config.decay_days)
            for p in procedural:
                await kv.set(KV.procedural, p.id, p)

            results["decay"] = {
                "semantic": len(semantic),
                "procedural": len(procedural),
            }

        logger.info(
            "consolidation pipeline completed (tier: %s, results: %s)", tier, results)
        return {"success": True, "results": results}

    sdk.register_function(
        {"id": "mem::consolidate-pipeline"},
        handle_consolidate_pipeline,
    )
