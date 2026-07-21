"""Sample agent: connects to the standalone MCP server (app/mcp_server.py)
and calls its run_insight_query tool to fetch data for a natural-language
request.

Usage:
    python -m app.mcp_server &            # start the MCP server (port 8001)
    python scripts/sample_agent.py "clients with balance over 1 million in Springfield"
"""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_SERVER_URL = "http://127.0.0.1:8001/mcp"


async def ask(query: str) -> dict:
    """Calls the MCP server's run_insight_query tool and returns its parsed JSON result."""
    async with streamable_http_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("run_insight_query", {"query": query})
            return json.loads(result.content[0].text)


def main() -> None:
    """Reads the query from argv and prints the tool's JSON result."""
    query = " ".join(sys.argv[1:]) or "clients with balance over 1 million in Springfield"
    result = asyncio.run(ask(query))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
