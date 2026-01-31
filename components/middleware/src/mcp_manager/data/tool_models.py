
from abc import abstractmethod
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Dict, Any, Callable, Optional, List, Awaitable

from mcp import ClientSession, StdioServerParameters, stdio_client
import mcp.types as mcp_types
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client


# ----------------------------------------------------------------------------------------------------------------------
# Backend server helpers
# ----------------------------------------------------------------------------------------------------------------------

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
    handler: Callable[[Dict[str, Any]], Awaitable[Any]]

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


class BackendServer:
    server_id: str
    tools: Dict[str, RegisteredTool]

    @abstractmethod
    def get_tools(self) -> List[RegisteredTool]:
        ...

# ----------------------------------------------------------------------------------------------------------------------
# Mock backend servers
# ----------------------------------------------------------------------------------------------------------------------

# TODO: this is a mock only and does not represent actual MCP servers. Replace/Implement!
class MockBackendServer(BackendServer):
    """
    Simple/Local in-process mock of an MCP server.

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

        # wrap sync -> async so everything looks async outside
        async def async_handler(args: Dict[str, Any]) -> Any:
            return handler(args)

        registered = RegisteredTool(
            id=fully_qualified_id,
            server_id=self.server_id,
            schema=schema,
            handler=async_handler,
        )
        self.tools[fully_qualified_id] = registered

    def get_tools(self) -> List[RegisteredTool]:
        return list(self.tools.values())


# ----------------------------------------------------------------------------------------------------------------------
# Remote backend servers
# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class MCPConnectionConfig:
    name: str
    transport: str  # "stdio", "sse", etc.

    # for stdio transport:
    command: Optional[str] = None
    args: List[str] = None
    env: Dict[str, str] = None

    # for HTTP/SSE transports:
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}
        if self.headers is None:
            self.headers = {}


class RemoteBackendServer(BackendServer):
    """
    Remote MCP backend that:
    - starts a server via stdio (e.g. docker run -i --rm mcp/youtube-transcript)
    - uses the official MCP ClientSession + stdio_client
    - exposes tools as RegisteredTool for your middleware
    """

    def __init__(self, server_id: str, config: MCPConnectionConfig) -> None:
        self.server_id = server_id
        self.config = config

        self._exit_stack = AsyncExitStack()
        self._session: Optional[ClientSession] = None

        self._tools_mcp: List[mcp_types.Tool] = []
        self._tools_wrapped: List[RegisteredTool] | None = None

    # ------------------------------------------------------------------
    # BackendServer interface
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        if self._session is not None:
            return  # already connected

        read_stream = write_stream = None

        if self.config.transport == "stdio":
            if not self.config.command:
                raise ValueError("MCPConnectionConfig.command must be set for remote MCP server")

            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env or None,
            )

            # stdio_client launches the process and gives us (read, write)
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                stdio_client(server=server_params)
            )
        elif self.config.transport == "sse":
            if not self.config.server_url:
                raise ValueError("server_url must be set for sse transport")

            # sse_client returns (read_stream, write_stream), same shape as stdio_client
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                sse_client(
                    url=self.config.server_url,
                    headers=self.config.headers or None,
                )
            )
        elif self.config.transport == "http":
            if not self.config.server_url:
                raise ValueError("server_url must be set for http transport")

            # streamable HTTP transport
            read_stream, write_stream, *_ = await self._exit_stack.enter_async_context(
                streamablehttp_client(
                    url=self.config.server_url,
                    headers=self.config.headers or None,
                )
            )

        else:
            raise NotImplementedError(f"Unsupported transport: {self.config.transport}")

        # ClientSession does handshake & JSON-RPC
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # MCP handshake (protocol + capabilities)
        await self._session.initialize()

        # Fetch tools once and cache
        list_result = await self._session.list_tools()
        self._tools_mcp = list_result.tools
        self._tools_wrapped = None  # force rebuild

    async def close(self) -> None:
        # Clean up the client/session and kill the subprocess
        await self._exit_stack.aclose()
        self._session = None
        self._tools_mcp = []
        self._tools_wrapped = None

    def get_tools(self) -> List[RegisteredTool]:
        """
        Wrap MCP tools into RegisteredTool objects with async handlers
        that call tools on this remote MCP server.
        Assumes connect() has already been awaited.
        """
        if self._tools_wrapped is not None:
            return self._tools_wrapped

        if self._session is None:
            # Optional: you can raise or return empty list
            raise RuntimeError("RemoteBackendServer not connected; call await connect() first")

        wrapped: List[RegisteredTool] = []

        for tool_def in self._tools_mcp:
            name = tool_def.name
            description = tool_def.description or ""
            input_schema = tool_def.inputSchema or {
                "type": "object",
                "additionalProperties": True,
            }

            schema = ToolSchema(
                name=name,
                description=description,
                input_schema=input_schema,
            )

            async def handler(
                args: Dict[str, Any],
                _tool_name: str = name,
            ) -> Dict[str, Any]:
                assert self._session is not None
                # call_tool returns a CallToolResult (Pydantic model)
                result = await self._session.call_tool(_tool_name, args)

                # Convert to plain dict for your outer MCP server
                # (model_dump is pydantic v2; use .dict() for v1)
                return result.model_dump()

            tool_id = f"{self.server_id}.{name}"

            wrapped.append(
                RegisteredTool(
                    id=tool_id,
                    server_id=self.server_id,
                    schema=schema,
                    handler=handler,
                )
            )

        self._tools_wrapped = wrapped
        return wrapped
