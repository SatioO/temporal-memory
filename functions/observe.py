import json
from typing import Optional
from iii import IIIClient
from functions.dedup import DedupMap
from functions.privacy import strip_private_data
from schema.domain import HookPayload
from state.kv import StateKV
from state.schema import generate_id


def register_observe_function(sdk: IIIClient, kv: StateKV, dedup_map: Optional[DedupMap], max_obs_per_session: int):
    async def handle_observe(payload: HookPayload):
        print(f"[graphmind] handle_observe received: {payload}")

        if (
            not payload
            or not isinstance(payload.get("session_id"), str)
            or not isinstance(payload.get("hook_type"), str)
            or not isinstance(payload.get("timestamp"), str)
        ):
            return {
                "success": False,
                "error": "Invalid payload: session_id, hook_type, and timestamp are required",
            }

        obs_id = generate_id("obs")

        dedup_hash = None

        if dedup_map:
            data = payload.get("data") if isinstance(
                payload, dict) else getattr(payload, "data", None)

            if isinstance(data, dict):
                d = data
            else:
                d = {}

            tool_name = d.get("tool_name") or payload.get("hook_type") if isinstance(
                payload, dict) else getattr(payload, "hook_type")

            dedup_hash = dedup_map.compute_hash(
                payload.get("session_id") if isinstance(
                    payload, dict) else getattr(payload, "session_id"),
                tool_name,
                d.get("tool_input"),
            )

            if dedup_map.is_duplicate(dedup_hash):
                return {
                    "deduplicated": True,
                    "session_id": payload.get("session_id") if isinstance(payload, dict) else getattr(payload, "session_id"),
                }

            try:
                sanitized_raw = str(payload.data)
                sanitized = strip_private_data(sanitized_raw)
                sanitized_raw = json.loads(sanitized)
            except:
                pass

    sdk.register_function({
        "id": "mem::observe",
        "description": "Capture and store a tool-use observation"
    }, handle_observe)
