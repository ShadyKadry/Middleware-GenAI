# Admin Ingestion and Retrieval (Gateway + Middleware)

## Overview
This document explains the admin ingestion flow, embedding model selection, and auto pre-search behavior that keeps retrieval consistent during chat. It is meant for new contributors and for anyone debugging data ingestion or retrieval.

Key ideas:
- The gateway handles uploads and UI.
- The middleware performs embeddings and writes to the vector DB.
- Qdrant stores vectors in per-model collections to avoid dimension conflicts.

## Goals
- Allow admins to upload large amounts of text data (.txt) from the web UI.
- Support multiple embedding models in parallel.
- Keep retrieval consistent by running search before the LLM answer (when enabled).

## Architecture
The system has two main pieces:
- Gateway (FastAPI + UI): collects uploads, runs chat, and calls middleware tools.
- Middleware (MCP server): embeds text, writes to Qdrant, and exposes tools.

Data is always written via the middleware tool `document_store.documents.upsert`. The gateway does not write to Qdrant directly.

## Embedding Models
Model registry lives in:
- `components/middleware/src/embedding_manager/embedding_backend.py`

Current models:
- `gemini-embedding-001` (real embeddings, requires `GEMINI_API_KEY`)
- `stub-256` (deterministic test model)

Important rule:
- The same `embedding_model` used for upload must be used for search. Otherwise, search hits a different collection and returns no results.

## Qdrant Collection Naming
Each embedding model has its own collection to support different vector sizes.

Collection naming:
- `collection = f"{corpus_id}__{model_id}"`

Implemented in:
- `components/middleware/src/mcp_manager/mcp_manager.py`

## Admin Upload Flow
1) Admin opens the upload panel in the UI.
2) Uploads a file (e.g., `.txt`, `.pdf`, `.pptx`, `.docx`) and selects a corpus and embedding model.
3) Gateway converts the file to Markdown (if needed), chunks it, and calls the middleware tool:
   - `document_store.documents.upsert`
4) Middleware embeds each chunk and writes to Qdrant.

Gateway upload endpoint:
- `POST /api/admin/documents/upload`

Files:
- UI: `components/gateway/templates/app.html`
- JS: `components/gateway/static/main.js`
- API: `components/gateway/app/main.py`

### File Conversion (Multi-type Support)
Non-text formats (PDF, PPTX, DOCX, etc.) are converted to Markdown using `markitdown` before chunking.

Why Markdown:
- A single normalized text format keeps downstream chunking and embedding logic simple.
- Most rich document formats can be flattened into readable, linear text.

If `markitdown` is missing, the upload API will return an error for non-text formats.

### Chunking Strategy
Chunking happens in the gateway before embeddings. Defaults:
- `chunk_size = 1200` characters
- `chunk_overlap = 200` characters

Rationale:
- Smaller chunks improve retrieval precision.
- Overlap keeps context across boundaries.

## Auto Pre-Search in Chat
Problem: LLMs do not always call tools.
Solution: When enabled, the gateway pre-calls search and injects results into the model prompt.

How it works:
1) Chat request includes `auto_search`, `corpus_id`, `embedding_model`, and `search_k`.
2) Gateway runs `document_store.documents.search`.
3) Results are injected into a system instruction for Gemini.
4) Gemini answers using that context.

Chat UI controls:
- Auto pre-search toggle
- Corpus ID
- Embedding model
- Top K

Files:
- UI: `components/gateway/templates/app.html`
- JS: `components/gateway/static/main.js`
- API + logic: `components/gateway/app/main.py`
- Gemini system instruction: `components/gateway/app/mcp_client.py`

## Stored Document Shape
Each chunk stored in Qdrant includes:
- `text`
- `user_id`
- `corpus_id`
- `embedding_model`
- `source` (file name)
- `chunk_index`
- `id` (file name + index)

## Tool Schemas
Middleware tools now accept `embedding_model`:
- `document_store.documents.upsert`
- `document_store.documents.search`

Tool definitions live in:
- `components/middleware/src/mcp_manager/mcp_manager.py`

## Environment Requirements
- `GEMINI_API_KEY` must be set for `gemini-embedding-001`.
- Qdrant must be running (`docker compose up`).
- `markitdown[all]` must be installed to ingest PDF/PPTX/DOCX and other rich formats.

## Troubleshooting
No search results:
- Verify the corpus ID and embedding model match the upload.
- Confirm the collection exists in Qdrant.
- Check that your `user_id` matches the stored payload.

Model answers without retrieval:
- Enable auto pre-search in chat.
- Verify `corpus_id` and `embedding_model` are set in the chat controls.

## Testing Checklist
1) Upload a file with corpus ID `demo_corpus` and `gemini-embedding-001`.
2) Enable auto pre-search in chat.
3) Ask a question contained in the uploaded text.
4) Confirm the answer uses the retrieved content.

## Where to Extend
Add more embedding models:
- Register in `components/middleware/src/embedding_manager/embedding_backend.py`
- Add to UI list in `components/gateway/app/main.py`

Adjust chunking:
- Update `chunk_text` in `components/gateway/app/main.py`
