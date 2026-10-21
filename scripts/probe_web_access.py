"""Probe the pi-web-access MCP server as a stdio client.

Verifies that an existing MCP server in this environment exposes a working
web search, so the VRE search adapter can reuse it instead of adding keys.
"""
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = r"C:/Users/verdu/.pi/agent/npm/node_modules/pi-web-access/dist/mcp-cli.js"


async def main() -> int:
    params = StdioServerParameters(command="node", args=[SERVER], env=None)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("server:", init.serverInfo)
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])
            res = await session.call_tool("web_search", {"query": "brutalist festival poster", "numResults": 3})
            text = "".join(c.text for c in res.content if getattr(c, "type", "") == "text")
            print("isError:", res.isError)
            print(text[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
