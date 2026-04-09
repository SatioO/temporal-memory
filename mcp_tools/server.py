
from iii import IIIClient

from state.kv import StateKV


def register_mcp_function(mcp, sdk: IIIClient, kv: StateKV):
    @mcp.tool
    async def memory_sessions():
        """List recent sessions with their status and observation counts."""
        return None
