from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from embedding_manager.embedding_backend import StubEmbeddingModel  # or GeminiEmbeddingModel
from embedding_manager.embedding_manager import EmbeddingManager
from db.qdrant_store import QdrantVectorStore


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



# ----------------------------------------------------------------------------------------------------------------------
# Mock backend servers
# ----------------------------------------------------------------------------------------------------------------------

# TODO: make it an interface/abstract class. dependency might get circular at some point
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

# ----------------------------------------------------------------------------------------------------------------------
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_PATH = Path(os.getenv("MW_BACKENDS_CONFIG", "backends.json"))

# Global in-memory config (can be reloaded at runtime)
BACKEND_CONFIG: Dict[str, Any] = {"backends": []}


def load_backend_config_from_disk() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        # fall back to empty or some built-in default
        return {"backends": []}

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # basic sanity
    if "backends" not in data or not isinstance(data["backends"], list):
        raise ValueError("Invalid backend config: missing 'backends' list")

    return data


def init_backend_config() -> None:
    global BACKEND_CONFIG
    BACKEND_CONFIG = load_backend_config_from_disk()
def get_mcp_servers(current_principal: Dict[str, Any]) -> List["MockBackendServer"]:
    """
    Returns all MCP servers that the current principal is allowed to access,
    based on BACKEND_CONFIG.
    """
    user_id: str = current_principal.get("user_id", "guest")
    roles: List[str] = current_principal.get("roles", [])

    backends: List[MockBackendServer] = []

    for backend_def in BACKEND_CONFIG.get("backends", []):
        if not backend_def.get("enabled", True):
            continue

        factory_name: str = backend_def.get("factory", "")
        factory = BACKEND_FACTORIES.get(factory_name)
        if factory is None:
            # Unknown factory name in config – skip or log
            continue

        required_roles: List[str] = backend_def.get("required_roles", [])
        allowed_users: List[str] = backend_def.get("allowed_users", [])

        has_role = not required_roles or any(r in roles for r in required_roles)
        user_allowed = not allowed_users or user_id in allowed_users

        if has_role and user_allowed:
            backend = factory()
            backends.append(backend)

    return backends


# TODO: replace with actual MCP servers available to the user (no user logic here yet). Create each as a single class and load based on user?
def build_mcp_servers(current_principal: dict) -> List[MockBackendServer]:
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
async def build_middleware_tool_registry(current_principal: dict) -> ToolRegistry:
    """
    Connect mock backends and aggregate their tools into a single registry.
    """
    registry = ToolRegistry()  # create empty registry
    backends = build_mcp_servers(current_principal)

    # add the document store backend
    backends.append(await build_embedding_manager())

    for backend in backends:
        for tool in backend.get_tools():
            registry.register(tool)

    return registry


async def build_embedding_manager() -> MockBackendServer:
    """
    Creates a new MCP server which deploys the embedding manager, and exposes two tools to the MCP client:
        - injecting data to DB (i.e. index_docs)
        - searching within the DB (i.e. search_docs)

    Handles all internal content management.
     """
    # TODO: make {store, model} dynamic based on user/prompt
    store = QdrantVectorStore()
    model = StubEmbeddingModel(dim=256)

    # 1. Bootstrap demo collection (idempotent: upsert overwrites if exists) TODO: start previous snapshot to reinstate DB state?!
    await store.bootstrap_demo_corpus(model, collection="demo_corpus")

    em = EmbeddingManager(embedding_model=model, vector_store=store)

    backend = MockBackendServer("document_store")

    async def upsert_docs(args: Dict[str, Any]) -> Dict[str, Any]:
        return await em.upsert_documents(
            user_id=args["user_id"],
            corpus_id=args["corpus_id"],
            documents=args["documents"],
        )

    async def search_docs(args: Dict[str, Any]) -> Dict[str, Any]:
        return await em.search_documents(
            user_id=args["user_id"],
            corpus_id=args["corpus_id"],
            query=args["query"],
            k=args.get("k", 5),
        )

    backend.add_tool(
        name="documents.index",
        description="Index documents into a semantic corpus.",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "corpus_id": {"type": "string"},
                "documents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["text"],
                    },
                },
            },
            "required": ["user_id", "corpus_id", "documents"],
        },
        handler=upsert_docs,
    )

    backend.add_tool(
        name="documents.search",
        description="Semantic search over a corpus.",
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "corpus_id": {"type": "string"},
                "query": {"type": "string"},
                "k": {"type": "integer"},
            },
            "required": ["user_id", "corpus_id", "query"],
        },
        handler=search_docs,
    )

    return backend

