#!/usr/bin/env python3
"""
Phase 1: MCP-compliant middleware server to be called by MCP Clients (e.g. DiveAI)

- Acts as a single MCP server for the host (e.g. DiveAI).
- Aggregates tools from two mocked "backend servers" via ToolRegistry.
- Implements proper MCP listTools and callTool using the Python SDK.

Transport: stdio (JSON-RPC over pipes, as required by MCP clients).
"""

import asyncio
import os
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from mcp_manager.mcp_manager import ToolRegistry, build_middleware_tool_registry

# --------------------------------------------------------------------
# Build aggregated registry from your backend "servers"
# --------------------------------------------------------------------
import sys
#print("Started middleware application...", file=sys.stderr)

registry: ToolRegistry | None = None

# create the MCP server instance (this is what DiveAI is talking to)
server = Server("diveai-middleware")


# --------------------------------------------------------------------
# MCP listTools handler
# --------------------------------------------------------------------
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    Expose all tools from the registry as MCP tools.

    Each registry tool is mapped 1:1 to an MCP Tool:
    - name:     tool.id    (e.g. "hr.get_policy")
    - desc:     tool.schema.description
    - inputSchema: tool.schema.input_schema (JSON Schema)
    """
    tools: list[types.Tool] = []

    for t in registry.list_all():
        # Fall back to very permissive schema if none is provided
        input_schema = t.schema.input_schema or {
            "type": "object",
            "additionalProperties": True,
        }

        tools.append(
            types.Tool(
                name=t.id,
                description=t.schema.description or "",
                inputSchema=input_schema,
                # If you have output schemas in your ToolRegistry,
                # you can add: outputSchema=t.schema.output_schema
            )
        )

    return tools


# --------------------------------------------------------------------
# MCP callTool handler
# --------------------------------------------------------------------
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Route MCP tool calls into the aggregated ToolRegistry.

    MCP already parsed 'arguments' per the inputSchema we returned in listTools.
    We just forward that dict into your existing handler.
    """
    tool = registry.get(name)
    if tool is None:
        # MCP spec expects errors to surface as exceptions – the SDK
        # turns this into a proper JSON-RPC error for the client.
        raise ValueError(f"Unknown tool: {name}")

    result = await tool.handler(arguments)

    # Support both sync and async handlers
    if asyncio.iscoroutine(result):
        result = await result

    # Low-level server expects a dict; it will validate it against
    # outputSchema if one was provided in listTools (optional).
    if not isinstance(result, dict):
        # If your tools return arbitrary JSON, you can relax this:
        # return {"result": result}
        return {"result": result}

    return result


# --------------------------------------------------------------------
# Entry point: stdio MCP server
# --------------------------------------------------------------------
async def run() -> None:
    """
    Run the MCP server over stdio.

    This replaces the old while True / json.loads loop – the SDK
    handles MCP handshake, JSON-RPC, batching, etc.
    """

    # obtain only subset of available MCP servers based on authenticated user
    global registry  # references the global variable at the beginning of the script
    username = os.getenv("MW_USERNAME", "user")
    roles = os.getenv("MW_ROLES", "admin")
    token = os.getenv("MW_TOKEN")

    current_principal = {
        "user_id": username,
        "roles": roles,
        "token": token,  # not used at the moment
    }
    #print(current_principal, file=sys.stderr)

    tool_registry: ToolRegistry = await build_middleware_tool_registry(current_principal) # currently done once at beginning of execution -> TODO: how will this be affected once multi-user access at same time has to be guaranteed
    registry = tool_registry

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="middleware-genai",  # could be anything
                server_version="0.1.0",  # could be anything
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())
