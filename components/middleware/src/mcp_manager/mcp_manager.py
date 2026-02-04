from typing import Any, Dict, List
from mcp_manager.data.tool_models import ToolRegistry, BackendServer
from mcp_manager.mcp_server_registry import backend_registry


async def get_mcp_servers(current_principal: Dict[str, Any]) -> List[BackendServer]:
    """
    Thin wrapper around BackendRegistry so other code doesn't depend
    on its internal implementation.
    """
    return await backend_registry.get_backends_for_principal(current_principal)


async def build_middleware_tool_registry(current_principal: dict) -> ToolRegistry:
    """
    Connect mock backends and aggregate their tools into a central registry.
    Builds the tool registry dynamically based on the calling user.
    """

    # create empty tool registry
    registry = ToolRegistry()

    # establish connection to the principal-accessible MCP servers
    backends: List[BackendServer] = await get_mcp_servers(current_principal)

    for backend in backends:
        for tool in backend.get_tools():
            registry.register(tool)

    return registry
