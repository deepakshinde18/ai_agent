"""Standalone MCP server exposing the fill_slots pipeline (sanitize ->
detect_intent -> lookup_intent -> fill_slots) as a single tool over
streamable HTTP.

Run directly (not mounted into the main FastAPI app):

    python -m app.mcp_server

Serves at http://<host>:<port>/mcp.
"""

from mcp.server.fastmcp import FastMCP

from app.graph.fill_slots_pipeline import run_fill_slots

mcp = FastMCP("insight-agent-fill-slots", stateless_http=True, host="0.0.0.0", port=8001)


@mcp.tool()
async def run_insight_query(query: str) -> dict:
    """Takes a natural-language insight request, resolves it to a configured
    report, builds its SQL from the matched insight's filter slots, runs it
    against the target database, and returns the fetched rows as JSON.

    Args:
        query: The user's natural-language request, e.g. "clients with
            balance over 1 million in Springfield".
    """
    return await run_fill_slots(query)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
