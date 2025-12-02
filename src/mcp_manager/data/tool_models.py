
from dataclasses import dataclass
from typing import Dict, Any, Callable, Optional, List


@dataclass
class ToolSchema:
    """Describes a tool in a simplified, MCP-like way."""
    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema-like


@dataclass
class RegisteredTool:
    """Tool as seen by the middleware."""
    id: str  # e.g. "hr.get_policy"
    server_id: str  # e.g. "hr"
    schema: ToolSchema
    handler: Callable[[Dict[str, Any]], Any]

class ToolRegistry:
    """Keeps track of all tools from all backend servers."""

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        if tool.id in self._tools:
            raise ValueError(f"Duplicate tool id: {tool.id}")
        self._tools[tool.id] = tool

    def list_all(self) -> List[RegisteredTool]:
        return list(self._tools.values())

    def get(self, tool_id: str) -> Optional[RegisteredTool]:
        return self._tools.get(tool_id)



# ----------------------------------------------------------------------------------------------------------------------
# Mock backend servers
# ----------------------------------------------------------------------------------------------------------------------

# TODO: this is a mock only and does not represent actual MCP servers. Replace/Implement!
class MockBackendServer:
    """
    Simple in-process mock of an MCP server.

    It has:
    - server_id (e.g. "hr")
    - tools: mapping from tool_name to (ToolSchema, handler)
    """

    def __init__(self, server_id: str) -> None:
        self.server_id = server_id
        self.tools: Dict[str, RegisteredTool] = {}

    def add_tool(self, name: str, description: str,
                 input_schema: Dict[str, Any],
                 handler: Callable[[Dict[str, Any]], Any]) -> None:
        fully_qualified_id = f"{self.server_id}.{name}"
        schema = ToolSchema(name=name,
                            description=description,
                            input_schema=input_schema)
        registered = RegisteredTool(
            id=fully_qualified_id,
            server_id=self.server_id,
            schema=schema,
            handler=handler,
        )
        self.tools[fully_qualified_id] = registered

    def get_tools(self) -> List[RegisteredTool]:
        return list(self.tools.values())