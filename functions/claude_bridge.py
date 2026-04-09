import os
from state.schema import KV
from state.kv import StateKV
from schema.domain import Memory
from schema.base import Model
from schema import CloudBridgeConfig, ProjectProfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from iii import IIIClient
from logger import get_logger

logger = get_logger("claude_bridge")


@dataclass(frozen=True)
class ClaudeBridgeSyncError(Model):
    success: bool
    error: str


@dataclass(frozen=True)
class ClaudeBridgeSyncResult(Model):
    success: bool
    path: Optional[str] = None
    lines: Optional[int] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ClaudeBridgeReadResult(Model):
    success: bool
    content: Optional[str] = None
    sections: Optional[Dict[str, str]] = None
    parsed: Optional[bool] = None
    error: Optional[str] = None


def _parse_memory_md(content: str) -> Dict[str, str]:
    """Parse ## sections from markdown into a dict of heading -> content string."""
    sections: Dict[str, str] = {}
    current_section: Optional[str] = None
    current_lines: List[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


def _serialize_to_memory_md(memories: list[Memory], project_summary: str, line_budget: int) -> str:
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
    async def handle_claude_bridge_sync(_: dict):
        logger.debug("handle_claude_bridge_sync triggered")
        if not config.enabled or config.memory_file_path is None:
            return ClaudeBridgeSyncError(success=False, error="Claude bridge not configured").to_dict()

        try:
            memories = await kv.list(KV.memories, Memory)
            latest_memories = [m for m in memories if m.is_latest]

            project_summary = ""
            if config.project_path:
                profile = await kv.get(KV.profiles, config.project_path, ProjectProfile)
                project_summary = profile.summary if profile is not None else ""

            md = _serialize_to_memory_md(
                latest_memories, project_summary, config.line_budget)

            dir_path = os.path.dirname(config.memory_file_path)
            os.makedirs(dir_path, exist_ok=True)

            with open(config.memory_file_path, "w", encoding="utf-8") as f:
                f.write(md)

            logger.info("synced to MEMORY.md path=%s memories=%d",
                        config.memory_file_path, len(latest_memories))

            return ClaudeBridgeSyncResult(
                success=True,
                path=str(config.memory_file_path),
                lines=len(md.split("\n")),
            ).to_dict()

        except Exception as err:
            return ClaudeBridgeSyncResult(success=False, error=str(err)).to_dict()

    async def handle_claude_bridge_read(_: dict):
        if not config.enabled or config.memory_file_path is None:
            return ClaudeBridgeReadResult(success=False, error="Claude bridge not configured").to_dict()

        try:
            if not os.path.exists(config.memory_file_path):
                return ClaudeBridgeReadResult(success=True, content="", parsed=False).to_dict()

            with open(config.memory_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            sections = _parse_memory_md(content)
            line_count = len(content.split("\n"))

            await kv.set(KV.claude_bridge, "last-read", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sections": sections,
                "lineCount": line_count,
            })

            logger.info("Claude bridge: read MEMORY.md path=%s lines=%d",
                        config.memory_file_path, line_count)

            return ClaudeBridgeReadResult(
                success=True,
                content=content,
                sections=sections,
            ).to_dict()

        except Exception as err:
            logger.error("Claude bridge read failed error=%s", str(err))
            return ClaudeBridgeReadResult(success=False, error=str(err)).to_dict()

    sdk.register_function(
        {"id": "mem::claude-bridge-sync"},
        handle_claude_bridge_sync,
    )

    sdk.register_function(
        {"id": "mem::claude-bridge-read"},
        handle_claude_bridge_read,
    )
