# Middleware for GenAI (Middleware Component)

---

## Purpose

The middleware is an MCP server layer that aggregates tools from:

- remote MCP servers (stdio / sse / http)
- one in-process local backend (`document_retrieval`)

It exposes a single MCP interface to the Gateway and returns only tools the current user is allowed to access.

---

## Runtime Topology

1. The Gateway starts `components/middleware/src/middleware_application.py` as a stdio subprocess.
2. Middleware receives `--user_id` and `--role` from the Gateway.
3. Middleware loads allowed MCP servers for that user from PostgreSQL view `vw_mcp_servers_effective_by_username`.
4. Middleware connects to each allowed server, collects tools, and exposes them through MCP `list_tools`/`call_tool`.

Core files:
- Entry point: `components/middleware/src/middleware_application.py`
- Registry builder: `components/middleware/src/mcp_manager/mcp_manager.py`
- Server loading and ACL query: `components/middleware/src/mcp_manager/mcp_server_loader.py`
- Backend abstraction (remote/local): `components/middleware/src/mcp_manager/data/tool_models.py`

---

## Data Sources

- **PostgreSQL (`pgvector` container)**
  - Source of truth for users, roles, MCP server registry, and corpus access metadata.
  - Middleware reads allowed servers through `middleware_ro` user.
- **Qdrant (`qdrant` container)**
  - Stores vectorized document chunks for semantic search.

Notes:
- A `PgVectorStore` implementation exists, but current ingestion flow defaults to `Qdrant`.
- `document_retrieval` currently uses `DEFAULT_DATABASE = "Qdrant"` unless a different DB is passed explicitly.

---

## Built-in Local Backend: `document_retrieval`

The local backend is implemented in:
- `components/middleware/src/mcp_manager/local_servers/document_retrieval.py`

Exposed tools:
- `document_retrieval.upsert`
- `document_retrieval.search`

Behavior:
- Embedding models are resolved via `embedding_backend.py`.
- Collection naming is per corpus + model: `<corpus_id>__<model_id>`.
- Search applies access filtering through `allowed_users` / `allowed_roles` metadata.

---

## Available Embedding Models

Implemented in:
- `components/middleware/src/embedding_manager/embedding_backend.py`

Current registry:
- `gemini-embedding-001`
- `stub-256`

---

## Setup Notes

From repository root:

1. Ensure `.env` contains:
   ```
   GEMINI_API_KEY=YOUR_API_KEY
   ```
2. Install dependencies:
   ```
   pip install -r components/middleware/requirements.txt
   ```
3. Start infrastructure:
   ```
   docker compose up
   ```
4. Start Gateway (which starts middleware on chat bootstrap):
   ```
   uvicorn components.gateway.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## Current Limitations / Open Points

- Chat sessions and middleware subprocess handles are stored in Gateway memory (`CHAT_SESSIONS`).
- Middleware server ACLs are DB-driven; there is no active file-based server registry in the current flow.
- Upload flow currently hardcodes corpus `database_model` to `Qdrant` in Gateway.
