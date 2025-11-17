from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional



# ------------------------------
# Data models
# ------------------------------


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



# ------------------------------
# Mock backend servers
# ------------------------------

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

# TODO: replace with actual MCP servers available to the user (no user logic here yet). Create each as a single class and load based on user?
def build_mock_backends() -> List[MockBackendServer]:
    """
    Build two simple backend servers with a couple of tools.
    This simulates "multiple MCP servers" in Phase 1.
    """
    # Backend 1: HR server
    hr = MockBackendServer("hr")

    def hr_get_policy(args: Dict[str, Any]) -> Dict[str, Any]:
        country = args.get("country", "UNKNOWN")
        # Stubbed text; in reality, you'd call a real MCP server here.
        return {
            "country": country,
            "policy": f"Stubbed vacation policy for {country}.",
        }

    hr.add_tool(
        name="get_policy",
        description="Get HR vacation policy for a country code. Use this tool whenever the user asks about HR vacation policy for any country. Do NOT guess. Always call this tool instead of answering from your own knowledge.",
        input_schema={
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "description": "ISO country code, e.g. 'DE'.",
                }
            },
            "required": ["country"],
        },
        handler=hr_get_policy,
    )

    # Backend 2: Jira server
    jira = MockBackendServer("jira")

    def jira_search(args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        # Stubbed list of tickets
        return {
            "query": query,
            "issues": [
                {"key": "PROJ-1", "summary": "Stubbed issue 1"},
                {"key": "PROJ-2", "summary": "Stubbed issue 2"},
            ],
        }

    jira.add_tool(
        name="search_issues",
        description="Search Jira issues by text query (stubbed).",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string.",
                }
            },
            "required": ["query"],
        },
        handler=jira_search,
    )

    # Backend 3: purpose server
    purpose = MockBackendServer("purpose")

    def find_purpose(args: Dict[str, Any]) -> Dict[str, Any]:
        topic = args.get("topic", "")
        return {
            "topic": topic,
            "purpose": f"The purpose of {topic} is to finish the Fraunhofer AMT project.",
        }

    purpose.add_tool(
        name="find_purpose",
        description="Search for the purpose of of a provided subject/topic.",
        input_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to find the purpose for.",
                }
            },
            "required": ["topic"],
        },
        handler=find_purpose,
    )

    return [hr, jira, purpose]


# TODO - User authentication: this should build the tool registry dynamically based on the calling user
def build_tool_registry() -> ToolRegistry:
    """
    Connect mock backends and aggregate their tools into a single registry.
    """
    registry = ToolRegistry()
    backends = build_mock_backends()

    for backend in backends:
        for tool in backend.get_tools():
            registry.register(tool)

    return registry

