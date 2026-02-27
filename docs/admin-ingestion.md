# Admin Ingestion and Retrieval (Gateway + Middleware)

## Overview
This document describes the current ingestion and retrieval implementation.
It focuses on what is implemented in code now, including access control, corpus handling, and auto pre-search.

Key ideas:
- Gateway handles admin UI, upload parsing/chunking, and chat orchestration.
- Middleware handles embedding + vector upsert/search via MCP tool calls.
- PostgreSQL stores users/roles, MCP server registry, and corpus metadata/access.
- Qdrant stores vectorized document chunks.

## Goals
- Allow admins to upload documents from the web UI.
- Support multiple embedding models.
- Keep chat retrieval stable with optional auto pre-search.
- Enforce user/role-based access for tools and corpora.

## Architecture
Main components:
- Gateway (FastAPI + frontend): `components/gateway`
- Middleware (MCP server): `components/middleware/src/middleware_application.py`
- Relational DB (PostgreSQL in `pgvector` container): users/roles/mcp_servers/corpora
- Vector DB (Qdrant): embedded chunks

Important separation:
- Gateway never writes vectors directly.
- Gateway always writes through middleware tool `document_retrieval.upsert`.

## Embedding Models
Model registry:
- `components/middleware/src/embedding_manager/embedding_backend.py`

Current models:
- `gemini-embedding-001`
- `stub-256`

Default model used by upload UI:
- `gemini-embedding-001`

## Database Backends
Database registry exists in:
- `components/middleware/src/embedding_manager/embedding_backend.py`

Available backends in code:
- `Qdrant`
- `Pgvector`

Current upload flow behavior:
- Gateway currently persists corpus `database_model` as `Qdrant` (hardcoded in upload endpoint).

## Collection Naming in Qdrant
To avoid dimension conflicts across models, vectors are stored in per-model collections:
- `<corpus_id>__<embedding_model>`

Implemented in:
- `components/middleware/src/mcp_manager/local_servers/document_retrieval.py`

## Tool APIs Used by Gateway
Current tool names:
- `document_retrieval.upsert`
- `document_retrieval.search`

Tool definitions:
- `components/middleware/src/mcp_manager/local_servers/document_retrieval.py`

## Admin Upload Flow
Endpoint:
- `POST /api/admin/documents/upload`

Implementation:
- `components/gateway/app/main.py`

Flow:
1. Admin submits upload form (file, corpus id, model, chunk settings, optional access rules).
2. Gateway checks admin role and chat session (`chat_session_id` is required).
3. File conversion:
   - `.txt/.md/.markdown`: direct decode
   - other formats (pdf/pptx/docx/...): converted via MarkItDown to Markdown
4. Gateway chunks text (`chunk_size`, `chunk_overlap`).
5. Gateway creates/validates corpus metadata in PostgreSQL.
6. Gateway calls `document_retrieval.upsert` via middleware MCP session.
7. Middleware embeds chunks and upserts vectors into Qdrant.

Corpus behavior:
- If corpus exists with mismatched parameters (`database_model`, `embedding_model`, `chunk_size`, `chunk_overlap`), upload is rejected as "Corpus already exists." and no write occurs.
- If corpus exists with matching parameters, upload appends/updates documents in the same corpus.
- For existing corpora, upload does not overwrite existing corpus ACL settings.

## File Conversion (Multi-type Support)
Conversion helper:
- `convert_upload_to_markdown` in `components/gateway/app/main.py`

Dependency:
- `markitdown` (in requirements)

If unavailable, non-text uploads fail with an explicit server error.

## Chunking Strategy
Chunking happens in Gateway before embedding.
Defaults:
- `chunk_size = 1200`
- `chunk_overlap = 200`

Function:
- `chunk_text` in `components/gateway/app/main.py`

## Auto Pre-Search in Chat
Chat endpoint:
- `POST /api/chat`

Behavior when `auto_search=true`:
1. Gateway loads selected corpora IDs from request.
2. For each corpus, Gateway validates user access (`get_user_and_corpus_or_404`).
3. Gateway calls `document_retrieval.search` once per corpus.
4. Results are normalized and merged/ranked (`select_best_chunks`).
5. Gateway builds a system instruction from best chunks and sends it to Gemini.

Important current behavior:
- Chat auto-search uses each corpus's configured embedding model from PostgreSQL.
- There is no chat-side embedding-model selector in the current UI.

Relevant files:
- `components/gateway/app/main.py`
- `components/gateway/app/mcp_client.py`
- `components/gateway/static/main.js`

## Access Control
There are two access control layers:

1) Tool/server access:
- Middleware loads only MCP servers granted to the user (directly or via role).
- Source: PostgreSQL view `vw_mcp_servers_effective_by_username`.

2) Corpus/document retrieval access:
- Gateway enforces corpus-level access (user/role) before search.
- Qdrant search applies payload filter on `allowed_users` / `allowed_roles`.

## Stored Chunk Shape (Qdrant Payload)
Each chunk payload contains at least:
- `id`
- `text`
- `source`
- `source_type`
- `chunk_index`
- `allowed_users`
- `allowed_roles`
- `uploaded_by`
- `corpus_id`
- `embedding_model`

## Environment Requirements
- `GEMINI_API_KEY` in `.env`
- Docker services running:
  - `pgvector` (relational metadata + ACL)
  - `qdrant` (vector storage)
- Dependencies installed from:
  - `components/middleware/requirements.txt`

## Testing Checklist
1. Start services: `docker compose up`.
2. Start app: `uvicorn components.gateway.app.main:app --reload --host 0.0.0.0 --port 8000`.
3. Log in as admin.
4. Bootstrap chat (open app page and wait for tools/corpora load).
5. Upload a document to a corpus.
6. Enable auto pre-search and select that corpus.
7. Ask a question contained in the uploaded text.
8. Verify response reflects retrieved content.

## Known Gaps / TODOs (from current code)
- Chat sessions are stored in-memory (`CHAT_SESSIONS`), not persisted.
- Upload currently reads full file into RAM before processing.
- Gateway currently hardcodes new corpus `database_model` to `Qdrant`.
