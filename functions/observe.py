import asyncio
import json
from typing import Optional
from logger import get_logger
from dataclasses import replace
from iii import IIIClient

from state.schema import KV, STREAM, generate_id
from state.kv import StateKV
from schema.domain import HookPayload, RawObservation, Session, HookType
from iii import TriggerRequest
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
            or not isinstance(payload.hook_type, HookType)
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
            hook_type=hook_type_str,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            user_prompt=user_prompt,
            raw=sanitized_raw,
        )

        async def handler():
            session = await kv.get(KV.sessions, payload.session_id, Session)

            if max_observations_per_session and max_observations_per_session > 0:
                count = session.observation_count if session else 0
                if count >= max_observations_per_session:
                    return {
                        "success": False,
                        "error": f"Session observation limit reached ({max_observations_per_session})",
                    }

            await kv.set(KV.observations(payload.session_id), obs_id, raw)

            if dedup_map and dedup_hash:
                dedup_map.record(dedup_hash)

            # await sdk.trigger_async({
            #     "function_id": "stream::set",
            #     "payload": {
            #         "stream_name": STREAM.name,
            #         "group_id": payload.session_id,
            #         "item_id": obs_id,
            #         "data": {"type": "raw", "observation": raw.to_dict()},
            #     }
            # })

            # await sdk.trigger_async({
            #     "function_id": "stream::set",
            #     "payload": {
            #         "stream_name": STREAM.name,
            #         "group_id": STREAM.viewer_group,
            #         "item_id": obs_id,
            #         "data": {"type": "raw", "observation": raw.to_dict(), "session_id": payload.session_id},
            #     }
            # })

            if session:
                await kv.set(
                    KV.sessions,
                    payload.session_id,
                    replace(
                        session, observation_count=session.observation_count + 1)
                )

            asyncio.create_task(sdk.trigger_async(TriggerRequest(
                function_id="mem::compress",
                payload={
                    "observation_id": obs_id,
                    "session_id": payload.session_id,
                    "raw": raw.to_dict(),
                },
            )))

            logger.debug("observation captured obs_id=%s session_id=%s hook=%s",
                         obs_id, payload.session_id, payload.hook_type)

            return {"observation_id": obs_id}

        return await with_keyed_lock(f"obs:{payload.session_id}", handler)

    sdk.register_function({
        "id": "mem::observe",
        "description": "Capture and store a tool-use observation"
    }, handle_observe)
