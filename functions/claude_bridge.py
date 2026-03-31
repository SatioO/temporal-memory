import os
from typing import Optional
from iii import IIIClient
from pydantic import BaseModel

from schema import CloudBridgeConfig
from schema.domain import Memory
from state.kv import StateKV
from state.schema import KV


class ClaudeBridgeSyncError(BaseModel):
    success: bool
    error: str


class ClaudeBridgeSyncResult(BaseModel):
    success: bool
    path: Optional[str] = None
    lines: Optional[int] = None
    error: Optional[str] = None


def serialize_to_memory_md(memories: list[Memory], project_summary: str, line_budget: str) -> str:
    lines: list[str] = []
    lines.append("# Agent Memory (auto-synced by graphmind)")
    lines.append("")

    if project_summary:
        lines.append("## Project Summary")
        lines.append(project_summary)
        lines.append("")

    lines.append("## Key Memories")
    lines.append("")

    sorted_memory = sorted(
        [memory for memory in memories if memory.is_latest],
        key=lambda m: m.strength,
        reverse=True,
    )

    for memory in sorted_memory:
        if len(lines) >= line_budget - 2:
            break

        lines.append(f"### {memory.title}")
        content_lines = memory.content.split("\n")

        for cl in content_lines:
            if len(lines) >= line_budget - 1:
                break
            lines.append(cl)

        lines.append("")

    return "\n".join(lines[:line_budget])


def register_claude_bridge_function(sdk: IIIClient, kv: StateKV, config: CloudBridgeConfig):
    async def handle_claude_bridge_sync(data_raw: dict):
        print(
            f"[graphmind] handle_claude_bridge_sync triggered")
        if not config.enabled or config.memory_file_path is None:
            return ClaudeBridgeSyncError(success=False, error="Claude bridge not configured")

        try:
            raw_memories = await kv.get_group(KV.memories)
            latest_memories = [
                memory for memory in raw_memories if memory.is_latest]

            # TODO: visit later to understand more
            project_summary = ""
            if config.project_path:
                profile = await kv.get(KV.profiles, config.project_path)
                project_summary = profile["summary"] if profile is not None else ""

            md = serialize_to_memory_md(
                latest_memories,
                project_summary,
                config.line_budget
            )

            dir_path = os.path.dirname(config.memory_file_path)
            os.makedirs(dir_path, exist_ok=True)

            with open(config.memory_file_path, "w", encoding="utf-8") as f:
                f.write(md)

            print(
                f"Claude bridge: synced to MEMORY.md \n path: {config.memory_file_path} \n memories: {len(latest_memories)}")

            return ClaudeBridgeSyncResult(
                success=True,
                path=str(config.memory_file_path),
                lines=len(md.split("\n"))
            )

        except Exception as err:
            return ClaudeBridgeSyncResult(success=False, error=str(err))

    sdk.register_function(
        {"id": "mem::claude-bridge::sync"},
        handle_claude_bridge_sync
    )
