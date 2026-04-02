from dataclasses import dataclass
import json
from typing import Any, Optional

from iii import IIIClient
from schema import Model, Session
from state.kv import StateKV
from state.schema import KV


@dataclass(frozen=True)
class MCPProperty(Model):
    type: str
    description: str


@dataclass(frozen=True)
class MCPToolInputSchema(Model):
    type: str
    properties: dict[str, MCPProperty]
    required: Optional[list[str]] = None


@dataclass(frozen=True)
class MCPTool(Model):
    name: str
    description: str
    input_schema: MCPToolInputSchema


@dataclass(frozen=True)
class MCPRequestPayload(Model):
    name: str
    arguments: dict[str, Any]


@dataclass
class MCPResponse(Model):
    status_code: int
    body: Any
    headers: Optional[dict[str, str]] = None


MCP_TOOLS: list[MCPTool] = [
    MCPTool(
        name="memory_sessions",
        description="List recent sessions with their status and observation count",
        input_schema=MCPToolInputSchema(
            type="object",
            properties={}
        )
    )
]


def register_mcp_function(sdk: IIIClient, kv: StateKV):
    async def handle_mcp_list(raw_data: dict) -> MCPResponse:
        return {"status_code": 200, "body": {"tools": MCP_TOOLS}}

    async def handle_mcp_call(raw_data: dict) -> MCPResponse:
        data: MCPRequestPayload = MCPRequestPayload.from_dict(raw_data)
        tool_name = data.name

        if tool_name == "memory_sessions":
            sessions = await kv.list(KV.sessions, Session)
            return {
                "status_code": 200,
                "body": {
                    "content": {
                        "type": "text",
                        "text": json.dumps(sessions)
                    }
                }
            }

        return {
            "status_code": 400,
            "body": {"error": f"Unknown tool: {tool_name}"},
        }

    sdk.register_function({
        "id": "mcp::tools::list"
    }, handle_mcp_list)

    sdk.register_function({
        "id": "mcp::tools::call"
    }, handle_mcp_call)
