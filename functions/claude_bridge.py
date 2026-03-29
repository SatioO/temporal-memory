import os
from dataclasses import dataclass
from iii import IIIClient

from schema import CloudBridgeConfig
from schema.domain import Memory
from state.kv import StateKV
from state.schema import KV


@dataclass
class ClaudeBridgeSyncError:
    success: bool
    error: str


@dataclass
class ClaudeBridgeSyncSuccess:
    success: bool
    path: str
    lines: str


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
            lines.push(cl)

        lines.append("")

    return "\n".join(lines[:line_budget])


def register_claude_bridge_function(sdk: IIIClient, kv: StateKV, config: CloudBridgeConfig):
    async def handle_claude_bridge_sync():
        if not config.enabled or config.memory_file_path is None:
            return ClaudeBridgeSyncError(success=False, error="Claude bridge not configured")

        try:
            memories: list[Memory] = await kv.list(KV.memories)
            latest_memories = [
                memory for memory in memories if memory.is_latest]

            # TODO: visit later to understand more
            project_summary = ""
            if config.project_path is not None:
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

            return ClaudeBridgeSyncSuccess(
                success=True,
                path=config.memory_file_path,
                lines=len(md.split("\n"))
            )

        except Exception as err:
            return ClaudeBridgeSyncError(success=False, error=str(err))

    sdk.register_function(
        {"id": "mem::claude-bridge-sync"},
        handle_claude_bridge_sync
    )
