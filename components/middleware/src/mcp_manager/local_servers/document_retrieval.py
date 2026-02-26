from typing import Dict, Any, Tuple
import re

from embedding_manager.embedding_backend import DEFAULT_EMBEDDING_MODEL_ID, get_embedding_model, get_database, \
    DEFAULT_DATABASE
from embedding_manager.embedding_manager import EmbeddingManager
from mcp_manager.data.tool_models import MockBackendServer


SERVER_KEY = "document_retrieval"

def _normalize_collection_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_")
    return cleaned or "default"


def build_collection_name(corpus_id: str, model_id: str) -> str:
    return f"{_normalize_collection_part(corpus_id)}__{_normalize_collection_part(model_id)}"  # todo model if is ambiguous as well. combination of model+db is identifier.


def build_backend():
    backend = MockBackendServer("document_retrieval")

    em_cache: Dict[Tuple[str, str], EmbeddingManager] = {}

    def get_manager(model_id: str, database_name: str) -> EmbeddingManager:
        key = (model_id, database_name)  # TODO simplistic approach where we assume only a single instance of each DB. multiple instances would require: host,port,etc. to be uniquely identified
        if key not in em_cache:
            model = get_embedding_model(model_id=model_id)
            store = get_database(database_name=database_name)
            em_cache[key] = EmbeddingManager(embedding_model=model, vector_store=store)
        return em_cache[key]

    async def upsert_docs(args: Dict[str, Any]) -> Dict[str, Any]:
        model_id = args.get("embedding_model") or DEFAULT_EMBEDDING_MODEL_ID
        database_name = args.get("database_name") or DEFAULT_DATABASE
        collection = build_collection_name(args["corpus_id"], model_id)  # todo redundant? corpus id should be sufficient
        em = get_manager(model_id=model_id, database_name=database_name)

        documents = []
        for doc in args["documents"]:
            doc_copy = dict(doc)
            doc_copy.setdefault("embedding_model", model_id)
            documents.append(doc_copy)

        return await em.upsert_documents(
            uploaded_by=args["user_id"],
            corpus_id=args["corpus_id"],
            documents=documents,
            collection_name=collection,
        )

    async def search_docs(args: Dict[str, Any]) -> Dict[str, Any]:
        model_id = args.get("embedding_model") or DEFAULT_EMBEDDING_MODEL_ID
        database_name = args.get("database_name") or DEFAULT_DATABASE
        collection = build_collection_name(args["corpus_id"], model_id)
        em = get_manager(model_id=model_id, database_name=database_name)

        return await em.search_documents(
            user_id=args["user_id"],
            user_role=args["user_role"],
            corpus_id=args["corpus_id"],
            query=args["query"],
            k=args.get("k", 5),
            collection_name=collection,
        )

    # storing/managing database is admin functionality only TODO how to handle this clean? server tools have different visibility levels -> upsert: admin or super-admin // search: all except guest
    backend.add_tool(
        name="upsert",
        description="Index or upsert documents into a semantic corpus.", # TODO more elaborate description could solve unreliable tool call
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "corpus_id": {"type": "string"},
                # "database_name": {"type": "string"}, TODO since missing it will always use defalut -> Qdrant
                "embedding_model": {"type": "string"},
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
        name="search",
        description="Semantic search over a corpus.", # TODO more elaborate description could solve unreliable tool call
        input_schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "corpus_id": {"type": "string"},
                # "database_name": {"type": "string"}, TODO since missing it will always use defalut -> Qdrant
                "embedding_model": {"type": "string"},
                "query": {"type": "string"},
                "k": {"type": "integer"},
            },
            "required": ["user_id", "corpus_id", "query"],
        },
        handler=search_docs,
    )

    return backend