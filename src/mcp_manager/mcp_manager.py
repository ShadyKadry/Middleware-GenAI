
from typing import Any, Dict, List

from embedding_manager.embedding_backend import StubEmbeddingModel  # or GeminiEmbeddingModel
from embedding_manager.embedding_manager import EmbeddingManager
from db.qdrant_store import QdrantVectorStore
from mcp_manager.data.tool_models import MockBackendServer, ToolRegistry
from mcp_manager.mcp_server_registry import backend_registry


def get_mock_mcp_servers(current_principal: Dict[str, Any]) -> List[MockBackendServer]:
    """
    Thin wrapper around BackendRegistry so other code doesn't depend
    on its internal implementation.
    """
    return backend_registry.get_backends_for_principal(current_principal)


async def build_middleware_tool_registry(current_principal: dict) -> ToolRegistry:
    """
    Connect mock backends and aggregate their tools into a central registry.
    Builds the tool registry dynamically based on the calling user.
    """
    # load MCP server registry
    backend_registry.load_config_from_disk()

    # create empty tool registry
    registry = ToolRegistry()

    # establish connection to the principal-accessible MCP servers
    backends = get_mock_mcp_servers(current_principal)

    # initialize MCP-based embedding manager which establishes connections to the principal-accessible vector DBs
    backends.append(await build_embedding_manager(current_principal))

    for backend in backends:
        for tool in backend.get_tools():
            registry.register(tool)

    return registry

# ----------------------------------------------------------------------------------------------------------------------

# TODO where to move this? in embedding_manager.py / here / as standalone class in local_servers
# FIXME: currently no user authentification - part of task 2.1?
async def build_embedding_manager(current_principal: dict) -> MockBackendServer:
    """
    Creates a new MCP server which deploys the embedding manager, and exposes two tools to the MCP client:
        - injecting data to DB (i.e. upsert_docs)
        - searching within the DB (i.e. search_docs)

    Handles all internal content management.
     """
    # TODO: make {store, model} dynamic based on user/prompt
    store = QdrantVectorStore()
    model = StubEmbeddingModel(dim=256)

    # FOR DEMO PURPOSE ONLY: Bootstrap demo collection (idempotent: upsert overwrites if exists) TODO: start previous snapshot to reinstate DB state?!
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
        name="documents.upsert",
        description="Index or upsert documents into a semantic corpus.",
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

