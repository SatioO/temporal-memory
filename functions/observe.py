import json
from typing import Optional
from logger import get_logger
from dataclasses import replace
from iii import IIIClient

from schema import CompressedObservation
from state.schema import KV, generate_id
from state.kv import StateKV
from schema.domain import HookPayload, RawObservation, Session, HookType
from functions.privacy import strip_private_data
from functions.dedup import DedupMap
from functions.common import with_keyed_lock

logger = get_logger("observe")


def register_observe_function(sdk: IIIClient, kv: StateKV, dedup_map: Optional[DedupMap], max_observations_per_session: int):
    async def handle_observe(raw_data: dict):
        payload: HookPayload = HookPayload.from_dict(raw_data)

        if (
            not payload
            or not isinstance(payload.session_id, str)
            or not isinstance(payload.hook_type, str)
            or not isinstance(payload.timestamp, str)
        ):
            return {
                "success": False,
                "error": "Invalid payload: session_id, hook_type, and timestamp are required",
            }

        obs_id = generate_id("obs")

        dedup_hash = None

        if dedup_map:
            d = payload.data if isinstance(payload.data, dict) else {}

            tool_name = d.get("tool_name") or payload.hook_type

            dedup_hash = dedup_map.compute_hash(
                payload.session_id,
                tool_name,
                d.get("tool_input"),
            )

            if dedup_map.is_duplicate(dedup_hash):
                return {
                    "deduplicated": True,
                    "session_id": payload.session_id,
                }

            try:
                json_str = json.dumps(payload.data)
                sanitized = strip_private_data(json_str)
                sanitized_raw = json.loads(sanitized)
            except Exception as e:
                logger.warning("sanitize fallback: %s", e)
                sanitized_raw = strip_private_data(str(payload.data))

            d = sanitized_raw if isinstance(sanitized_raw, dict) else {}
            hook_type_str = payload.hook_type

            tool_name = None
            tool_input = None
            tool_output = None
            user_prompt = None

            if hook_type_str in (HookType.POST_TOOL_USE, HookType.POST_TOOL_FAILURE):
                tool_name = d.get("tool_name")
                tool_input = d.get("tool_input")
                tool_output = d.get("tool_response") or d.get("error")

            if hook_type_str == HookType.PROMPT_SUBMIT:
                user_prompt = d.get("prompt")

            raw = RawObservation(
                id=obs_id,
                session_id=payload.session_id,
                timestamp=payload.timestamp,
                hook_type=HookType(hook_type_str),
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                user_prompt=user_prompt,
                raw=None,  # TODO: kept this to none to avoid dumping lot of data to cache
            )

            async def handler():
                if max_observations_per_session and max_observations_per_session > 0:
                    existing = await kv.list(KV.observations(payload.session_id), CompressedObservation)
                    if len(existing) >= max_observations_per_session:
                        return {
                            "success": False,
                            "error": f"Session observation limit reached ({max_observations_per_session})",
                        }

                # TODO: Decide if this is required
                await kv.set(KV.observations(payload.session_id), obs_id, raw)

                if dedup_map and dedup_hash:
                    dedup_map.record(dedup_hash)

                session = await kv.get(KV.sessions, payload.session_id, Session)
                if session:
                    await kv.set(
                        KV.sessions,
                        payload.session_id,
                        replace(
                            session, observation_count=session.observation_count + 1)
                    )

                await sdk.trigger_async({
                    "function_id": "mem::compress",
                    "payload": {
                        "observation_id": obs_id,
                        "session_id": payload.session_id,
                        "raw": raw,
                    },
                    "action": "void"
                })

                logger.debug("observation captured obs_id=%s session_id=%s hook=%s",
                             obs_id, payload.session_id, payload.hook_type)

                return {"observation_id": obs_id}

            return await with_keyed_lock(f"obs:{payload.session_id}", handler)

    sdk.register_function({
        "id": "mem::observe",
        "description": "Capture and store a tool-use observation"
    }, handle_observe)
