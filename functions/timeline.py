import re
import datetime
from dataclasses import dataclass
from logger import get_logger
from typing import Any, Dict, List, Optional
from iii import IIIClient
from state.schema import KV
from schema import CompressedObservation, Model, Session
from state.kv import StateKV

logger = get_logger("timeline")


@dataclass
class TimelinePayload(Model):
    anchor: str
    project: Optional[str] = None
    before: Optional[int] = None
    after: Optional[int] = None


_ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")


def parse_ts(ts: str) -> int:
    return int(datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)


def register_timeline_function(sdk: IIIClient, kv: StateKV):
    async def handle_timeline(raw_data: dict):
        data = TimelinePayload.from_dict(raw_data)

        before = data.before or 5
        after = data.after or 5

        anchor_time: int = 0

        if _ISO_PATTERN.match(data.anchor):
            anchor_time = int(datetime.datetime.fromisoformat(
                data.anchor).timestamp() * 1000)
        else:
            search_results = await find_by_keyword(kv, data.anchor, data.project)

            if len(search_results) == 0:
                return {
                    "entries": [],
                    "anchor": data.anchor,
                    "reason": "no_match",
                }

            anchor_time = parse_ts(search_results[0].timestamp)

        sessions = await kv.list(KV.sessions, Session)

        filtered = (
            [s for s in sessions if s.project == data.project]
            if data.project
            else sessions
        )

        all_obs: List[Dict[str, Any]] = []

        for session in filtered:
            observations = await kv.list(KV.observations(session.id), CompressedObservation)

            for obs in observations:
                if obs.title and obs.timestamp:
                    all_obs.append({
                        **obs.to_dict(),
                        "sid": session.id,
                    })

        # sort ascending by timestamp
        all_obs.sort(key=lambda x: parse_ts(x["timestamp"]))

        # find closest to anchor_time
        anchor_idx = 0
        min_dist = float("inf")

        for i, obs in enumerate(all_obs):
            dist = abs(parse_ts(obs["timestamp"]) - anchor_time)
            if dist < min_dist:
                min_dist = dist
                anchor_idx = i

        start_idx = max(0, anchor_idx - before)
        end_idx = min(len(all_obs) - 1, anchor_idx + after)

        entries = []

        for i in range(start_idx, end_idx + 1):
            obs = all_obs[i]
            sid = obs["sid"]

            observation = {k: v for k, v in obs.items() if k != "sid"}

            entries.append({
                "observation": observation,
                "session_id": sid,
                "relative_position": i - anchor_idx,
            })

        logger.info(
            "Timeline retrieved (anchor: %s, entries: %s)", data.anchor, len(
                entries)
        )

        return {
            "entries": entries,
            "anchor_index": anchor_idx - start_idx,
        }

    sdk.register_function({
        "id": "mem::timeline",
        "description": "Get chronological observations around an anchor point"
    }, handle_timeline)


async def find_by_keyword(kv: StateKV, keyword: str, project: Optional[str] = None) -> List[CompressedObservation]:
    sessions = await kv.list(KV.sessions, Session)

    filtered = [s for s in sessions if s.project ==
                project] if project is not None else sessions

    lower = keyword.lower()
    matches: List[CompressedObservation] = []

    for session in filtered:
        observations = await kv.list(KV.observations(
            session.id), CompressedObservation)

        for obs in observations:
            if (
                (obs.title and lower in obs.title.lower()) or
                (obs.narrative and lower in obs.narrative.lower()) or
                (obs.concepts and any(lower in c.lower()
                 for c in obs.concepts))
            ):
                matches.append(obs)

    matches.sort(
        key=lambda x: datetime.datetime.fromisoformat(
            x.timestamp.replace("Z", "+00:00")),
        reverse=True,
    )

    return matches
