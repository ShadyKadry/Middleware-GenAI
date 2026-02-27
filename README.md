# Middleware-GenAI

End-to-end Gateway + Middleware project for MCP-based tool orchestration and RAG retrieval.

This repository contains:
- A web Gateway (FastAPI + frontend) for login, chat, and admin operations.
- A Middleware MCP server that aggregates user-allowed MCP backends.
- PostgreSQL for identity, access control, MCP server registry, and corpus metadata.
- Qdrant for vector storage and semantic retrieval.

## Repository Structure

- `components/gateway` - web app (API, auth, UI, chat orchestration)
- `components/middleware` - middleware MCP server and retrieval backend
- `docker-compose.yml` - local infrastructure services (PostgreSQL/pgvector + Qdrant)
- `docker/pgvector-init` - DB schema, seed data, and DB security setup
- `docs/admin-ingestion.md` - ingestion and retrieval behavior/details

## Quick Setup (Local)

From repository root:

1. Create `.env` with Gemini API key:
   ```bash
   GEMINI_API_KEY=YOUR_API_KEY
   ```
2. Create and activate virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r components/middleware/requirements.txt
   ```
4. Start infrastructure:
   ```powershell
   docker compose up
   ```
5. Start Gateway:
   ```powershell
   uvicorn components.gateway.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
6. Open:
   - `http://127.0.0.1:8000`

Default seeded admin (fresh Postgres volume):
- Username: `Admin`
- Password: `adminpass`

## High-Level Flow

1. User logs in to Gateway (`/api/login` or `/api/auth/login`).
2. UI bootstraps chat (`/api/chat/bootstrap`):
   - Gateway creates chat session.
   - Gateway starts middleware subprocess over MCP stdio.
   - Middleware loads only user-allowed MCP servers/tools from PostgreSQL.
3. User sends chat request (`/api/chat`):
   - Optional auto pre-search across selected corpora.
   - Gateway calls middleware retrieval tools.
   - Gateway calls Gemini and returns response.
4. Admin upload (`/api/admin/documents/upload`):
   - File converted to Markdown if needed.
   - Text chunked and upserted through middleware tool calls.
   - Vectors stored in Qdrant; corpus metadata/access stored in PostgreSQL.

## Current Databases and Responsibilities

- PostgreSQL (`pgvector` service):
  - users, roles
  - MCP server registry and role/user access mappings
  - corpus metadata and corpus access mappings
- Qdrant (`qdrant` service):
  - embedded chunks for semantic retrieval
  - payload-based access filtering (`allowed_users`, `allowed_roles`)

Note: Pgvector storage backend exists in code, but current ingestion flow defaults to Qdrant.

## Tooling and Retrieval

Current local retrieval backend exposes:
- `document_retrieval.upsert`
- `document_retrieval.search`

Collection naming for model separation:
- `<corpus_id>__<embedding_model>`

## Documentation Map

- Gateway-focused docs: `components/gateway/README_gateway.md`
- Middleware-focused docs: `components/middleware/README.md`
- Ingestion/retrieval details: `docs/admin-ingestion.md`
- Legacy optional debug wrapper: `debug/README.md`

