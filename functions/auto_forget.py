import dataclasses
from dataclasses import dataclass, field
import time
from typing import List, Optional
from iii import IIIClient

from schema import CompressedObservation, Memory, Model, Session
from state.kv import StateKV
from state.schema import KV, jaccard_similarity, parse_ts


@dataclass(frozen=True)
class AutoForgetPayload(Model):
    dry_run: Optional[bool] = False


@dataclass(frozen=True)
class Contradiction(Model):
    memory_a: str
    memory_b: str
    similarity: float


@dataclass(frozen=True)
class AutoForgetResult(Model):
    ttl_expired: List[str] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    low_value_obs: List[str] = field(default_factory=list)
    dry_run: bool = False


MS_PER_DAY = 24 * 60 * 60 * 1000
CONTRADICTION_THRESHOLD = 0.9


def register_auto_forget_function(sdk: IIIClient, kv: StateKV):
    async def handle_auto_forget(raw_data: dict) -> AutoForgetResult:
        data = AutoForgetPayload.from_dict(raw_data)
        # fix: now resolves correctly with "import time"
        now = int(time.time() * 1000)

        result = AutoForgetResult(
            ttl_expired=[],
            contradictions=[],
            low_value_obs=[],
            dry_run=data.dry_run,
        )

        memories = await kv.list(KV.memories, Memory)

        for mem in memories:
            if mem.forget_after:
                expiry = parse_ts(mem.forget_after)

                if now > expiry:
                    result.ttl_expired.append(mem.id)

                    if not data.dry_run:
                        await kv.delete(KV.memories, mem.id)

        latest_memories = [m for m in memories if m.is_latest is not False]

        for i in range(len(latest_memories)):
            for j in range(i + 1, len(latest_memories)):
                m1 = latest_memories[i]
                m2 = latest_memories[j]

                sim = jaccard_similarity(
                    m1.content.lower(),
                    m2.content.lower(),
                )

                if sim > CONTRADICTION_THRESHOLD:
                    result.contradictions.append(
                        Contradiction(
                            memory_a=m1.id,
                            memory_b=m2.id,
                            similarity=sim,
                        )
                    )

                    if not data.dry_run:
                        t1 = parse_ts(m1.created_at)
                        t2 = parse_ts(m2.created_at)

                        older = m1 if t1 < t2 else m2
                        older_updated = dataclasses.replace(
                            older, is_latest=False)

                        await kv.set(KV.memories, older_updated.id, older_updated)

        sessions = await kv.list(KV.sessions, Session)

        for session in sessions:
            try:
                observations = await kv.list(KV.observations(session.id), CompressedObservation)
            except Exception:
                observations = []

            for obs in observations:
                if not obs.timestamp:
                    continue

                age = now - parse_ts(obs.timestamp)

                if age > 180 * MS_PER_DAY and (obs.importance if obs.importance is not None else 5) <= 2:
                    result.low_value_obs.append(obs.id)

                    if not data.dry_run:
                        try:
                            await kv.delete(KV.observations(session.id), obs.id)
                        except Exception:
                            pass

        return result

    sdk.register_function(
        {
            "id": "mem::auto_forget",
            "description": "Auto-forget expired (TTL), contradictory, and low-value data",
        },
        handle_auto_forget
    )
