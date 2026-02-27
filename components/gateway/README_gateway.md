# Middleware for GenAI (Gateway)

---

## Prerequisites

Before starting, ensure the following are available:

- **Python 3.12**
- **Docker Desktop** (Docker daemon running)
- **Google AI API key** (`GEMINI_API_KEY`)
- **Repository checkout** of this project

---

## Setup

1. From the repository root, add your API key to `.env`:
   ```
   GEMINI_API_KEY=YOUR_API_KEY
   ```
2. Create and activate a virtual environment (if not already available):
   ```
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```
   pip install -r components/middleware/requirements.txt
   ```
4. Start infrastructure services (PostgreSQL/pgvector + Qdrant):
   ```
   docker compose up
   ```
5. Start the Gateway app:
   ```
   uvicorn components.gateway.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
6. Open `http://127.0.0.1:8000` and log in.

Seeded default login (fresh DB initialization):
- `Admin` / `adminpass`

Note: if the Postgres volume already existed, credentials and seed data may differ from defaults.

---

## Architecture At A Glance

- **Gateway (`components/gateway`)**
  - FastAPI app + HTML/JS UI
  - Handles login/JWT cookies
  - Manages chat sessions and UI state bootstrapping
  - Provides admin APIs (user creation, MCP server registration, document upload)
- **Middleware (`components/middleware`)**
  - Started by Gateway as an MCP subprocess per chat session
  - Builds user-specific tool registry from allowed MCP servers
- **Relational DB (PostgreSQL service `pgvector`)**
  - Stores users, roles, MCP server registry, corpus metadata and access control
- **Vector DB (Qdrant service `qdrant`)**
  - Stores embedded document chunks used by retrieval

---

## Main Workflows

### 1) Login + bootstrap

1. User logs in via `/api/login` (alias of `/api/auth/login`).
2. Gateway issues JWT cookies.
3. UI calls `/api/chat/bootstrap`:
   - creates a chat session
   - starts middleware subprocess via MCP
   - loads available tools for this user
4. UI calls `/api/corpora/bootstrap` to load corpora accessible to this user.

### 2) Chat

1. User sends message via `/api/chat`.
2. Optional auto pre-search (`auto_search=true`):
   - Gateway calls `document_retrieval.search` for selected corpora.
   - Results are normalized/ranked and injected as system instruction.
3. Gateway calls Gemini with selected tools and returns final text response.

### 3) Admin document ingestion

1. Admin uploads document via `/api/admin/documents/upload`.
2. Gateway converts non-text files to Markdown using MarkItDown.
3. Content is chunked and upserted through middleware tool `document_retrieval.upsert`.
4. Vectors are stored in Qdrant; corpus metadata/access is stored in PostgreSQL.

### 4) Admin MCP server registration

1. Admin submits MCP server config via `/api/admin/mcp-servers`.
2. Config is persisted in PostgreSQL.
3. Newly registered tools become available after re-bootstrap/new chat session.

---

## UI Entry Points

- Login page: `/`
- Main app: `/app`
- Main client script: `components/gateway/static/main.js`
- Main template: `components/gateway/templates/app.html`

---

## Sequence Diagram

![System sequence diagram](../../docs/diagrams/sequence_flow_chart.png)
