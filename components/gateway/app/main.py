import json
import logging
import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import List, Any, Dict, Optional, Set

from fastapi import (
    FastAPI,
    Request,
    Form,
    HTTPException,
    Depends,
    UploadFile,
    File,
)
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.genai.types import Tool
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .mcp_client import MCPClient
from .db.session import engine, Base, get_db
from .db.models import User
from .auth.jwt_auth import (
    create_token,
    decode_token,
    set_auth_cookies,
    clear_auth_cookies,
    current_principal,
    get_refresh_cookie,
    ACCESS_MINUTES,
    REFRESH_DAYS,
)

# gateway project root
BASE_DIR = Path(__file__).resolve().parent.parent

# todo: where should ongoing sessions be saved? DB? in code is suboptimal security-wise...
CHAT_SESSIONS: Dict[str, Dict[str, Any]] = {}

# minimal server-side invalidation for refresh tokens (iteration 1)
REVOKED_REFRESH_TOKENS: Set[str] = set()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# embedding models exposed in the admin UI
EMBEDDING_MODELS = [
    {"id": "gemini-embedding-001", "label": "Gemini embedding-001"},
    {"id": "stub-256", "label": "Stub (deterministic, 256d)"},
]
DEFAULT_EMBEDDING_MODEL_ID = "gemini-embedding-001"

# middleware backend registry config
BACKENDS_CONFIG_PATH = (
    BASE_DIR.parent.parent
    / "components"
    / "middleware"
    / "src"
    / "mcp_manager"
    / "local_servers"
    / "backends.json"
)


#######################################
### ---> Helper classes & functions ###
#######################################

class ToolUI(BaseModel):
    name: str
    description: str = ""

class BootstrapOut(BaseModel):
    chat_session_id: str
    tools_ui: List[ToolUI]

class ChatIn(BaseModel):
    message: str
    selected_tools: Optional[List[str]] = None
    chat_session_id: Optional[str] = None
    auto_search: Optional[bool] = False
    corpus_id: Optional[str] = None
    embedding_model: Optional[str] = None
    search_k: Optional[int] = 5

class AdminCreateUserIn(BaseModel):
    username: str
    password: str
    role: str = "user"  # "user" or "admin"


def filter_tools(all_tools, allowed_names: set[str]):
    filtered = []
    for tool in all_tools:
        fds = getattr(tool, "function_declarations", None) or []
        kept = [fd for fd in fds if fd.name in allowed_names]
        if kept:
            filtered.append(Tool(function_declarations=kept))
    return filtered


def _principal_from_request_optional(request: Request) -> Optional[dict]:
    # Used only for template routing decisions; API auth uses Depends(current_principal)
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except HTTPException:
        return None


def _require_admin(principal: dict) -> None:
    if principal.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


async def _get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one_or_none()


def _ensure_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(",", ";").split(";")]
        return [p for p in parts if p]
    raise HTTPException(status_code=400, detail="Invalid list field")


def load_backends_config() -> Dict[str, Any]:
    if not BACKENDS_CONFIG_PATH.exists():
        return {"backends": []}
    with BACKENDS_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_backends_config(config: Dict[str, Any]) -> None:
    BACKENDS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BACKENDS_CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def normalize_backend_def(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = payload.get("name")
    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="name is required")

    kind = payload.get("kind") or "remote_mcp"
    if kind not in {"remote_mcp", "local_mcp_mock"}:
        raise HTTPException(status_code=400, detail="Unsupported kind")

    backend: Dict[str, Any] = {
        "name": name.strip(),
        "kind": kind,
        "enabled": bool(payload.get("enabled", True)),
        "required_roles": _ensure_list(payload.get("required_roles")),
        "allowed_users": _ensure_list(payload.get("allowed_users")),
    }

    if kind == "local_mcp_mock":
        factory = payload.get("factory")
        if not factory:
            raise HTTPException(status_code=400, detail="factory is required for local_mcp_mock")
        backend["factory"] = str(factory)
        return backend

    transport = payload.get("transport") or "stdio"
    if transport not in {"stdio", "sse", "http"}:
        raise HTTPException(status_code=400, detail="Unsupported transport")
    backend["transport"] = transport

    if transport == "stdio":
        command = payload.get("command")
        if not command:
            raise HTTPException(status_code=400, detail="command is required for stdio transport")
        backend["command"] = str(command)
        args = payload.get("args") or []
        backend["args"] = _ensure_list(args)
        env = payload.get("env") or {}
        if not isinstance(env, dict):
            raise HTTPException(status_code=400, detail="env must be an object")
        backend["env"] = env
    else:
        server_url = payload.get("server_url")
        if not server_url:
            raise HTTPException(status_code=400, detail="server_url is required for remote transport")
        backend["server_url"] = str(server_url)
        headers = payload.get("headers") or {}
        if not isinstance(headers, dict):
            raise HTTPException(status_code=400, detail="headers must be an object")
        backend["headers"] = headers

    return backend


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    size = max(1, chunk_size)
    overlap = max(0, min(overlap, size - 1))
    step = size - overlap

    chunks = []
    for start in range(0, len(cleaned), step):
        chunk = cleaned[start:start + size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def extract_tool_payload(result: Any) -> Any:
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                text = first["text"]
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
    return result


def convert_upload_to_markdown(filename: str, data: bytes) -> str:
    if not data:
        raise HTTPException(400, "Empty file")

    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return data.decode("utf-8", errors="replace")

    try:
        from markitdown import MarkItDown
    except Exception as exc:
        raise HTTPException(
            500,
            "markitdown is not installed. Install it with: pip install 'markitdown[all]'",
        ) from exc

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()
        converter = MarkItDown()
        result = converter.convert(tmp.name)
        markdown = getattr(result, "text_content", None) or getattr(result, "text", None)
        if not markdown:
            raise HTTPException(500, "Conversion returned empty content")
        return markdown
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def build_retrieval_instruction(payload: Any) -> str:
    summary = payload
    if isinstance(payload, dict) and "results" in payload:
        summary_results = []
        for result in payload.get("results", []):
            meta = result.get("metadata", {}) if isinstance(result, dict) else {}
            summary_results.append({
                "id": result.get("id") if isinstance(result, dict) else None,
                "score": result.get("score") if isinstance(result, dict) else None,
                "text": meta.get("text"),
                "source": meta.get("source"),
                "chunk_index": meta.get("chunk_index"),
            })
        summary = {
            "query": payload.get("query"),
            "corpus_id": payload.get("corpus_id"),
            "results": summary_results,
        }

    context_json = json.dumps(summary, ensure_ascii=True, indent=2)
    return (
        "Use the retrieved context below to answer the user's question. "
        "If the context does not contain the answer, say you could not find it in the corpus.\n"
        f"Retrieved context (JSON):\n{context_json}"
    )


#######################################
### ---> The actual application     ###
#######################################
app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def on_shutdown():
    # cleanup MCP subprocess sessions
    for sess in list(CHAT_SESSIONS.values()):
        mcp = sess.get("mcp")
        if mcp:
            try:
                await mcp.cleanup()
            except Exception:
                pass
    CHAT_SESSIONS.clear()


#######################################
### ---> Pages (templates)          ###
#######################################
@app.get("/")
def login_page(request: Request):
    principal = _principal_from_request_optional(request)
    if principal:
        return RedirectResponse("/app", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/app")
def app_page(request: Request):
    principal = _principal_from_request_optional(request)
    if not principal:
        return RedirectResponse("/", status_code=302)

    # subject is username in this iteration
    username = principal["sub"]
    return templates.TemplateResponse(
        "app.html",
        {
            "request": request,
            "user": username,
        },
    )


#######################################
### ---> Auth API (JWT cookies)     ###
#######################################
@app.post("/api/auth/login")
async def auth_login(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await _get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=401, detail="Not allowed")
    if not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong password")

    access = create_token(
        subject=user.username,
        role=user.role,
        expires_delta=__import__("datetime").timedelta(minutes=ACCESS_MINUTES),
        token_type="access",
    )
    refresh = create_token(
        subject=user.username,
        role=user.role,
        expires_delta=__import__("datetime").timedelta(days=REFRESH_DAYS),
        token_type="refresh",
    )

    resp = JSONResponse({"ok": True})
    set_auth_cookies(resp, access, refresh)
    return resp


@app.post("/api/auth/refresh")
def auth_refresh(refresh_token: str = Depends(get_refresh_cookie)):
    if refresh_token in REVOKED_REFRESH_TOKENS:
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    username = payload["sub"]
    role = payload.get("role", "user")

    access = create_token(
        subject=username,
        role=role,
        expires_delta=__import__("datetime").timedelta(minutes=ACCESS_MINUTES),
        token_type="access",
    )
    new_refresh = create_token(
        subject=username,
        role=role,
        expires_delta=__import__("datetime").timedelta(days=REFRESH_DAYS),
        token_type="refresh",
    )

    # rotate refresh: revoke old, set new
    REVOKED_REFRESH_TOKENS.add(refresh_token)

    resp = JSONResponse({"ok": True})
    set_auth_cookies(resp, access, new_refresh)
    return resp


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    old_refresh = request.cookies.get("refresh_token")
    if old_refresh:
        REVOKED_REFRESH_TOKENS.add(old_refresh)

    resp = JSONResponse({"ok": True})
    clear_auth_cookies(resp)
    return resp


@app.get("/api/auth/me")
def auth_me(principal: dict = Depends(current_principal)):
    return {"user": principal["sub"], "role": principal.get("role", "user")}


# Backward-compatible aliases for existing templates/static JS (keeps current UI working)
@app.post("/api/login")
async def login_alias(username: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    return await auth_login(username=username, password=password, db=db)

@app.post("/api/logout")
def logout_alias(request: Request):
    return auth_logout(request)

@app.get("/api/me")
def me_alias(principal: dict = Depends(current_principal)):
    return auth_me(principal)


#######################################
### ---> Admin API                  ###
#######################################
@app.post("/api/admin/users")
async def admin_create_user(
    payload: AdminCreateUserIn,
    principal: dict = Depends(current_principal),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(principal)

    role = payload.role.strip().lower()
    if role not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="role must be 'user' or 'admin'")

    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    if not payload.password:
        raise HTTPException(status_code=400, detail="password required")

    existing = await _get_user_by_username(db, username)
    if existing:
        raise HTTPException(status_code=409, detail="username already exists")

    user = User(
        username=username,
        password_hash=pwd_context.hash(payload.password),
        role=role,
    )
    db.add(user)
    await db.commit()

    return {"ok": True, "username": username, "role": role}


@app.post("/api/admin/mcp-servers")
async def register_mcp_server(
    payload: Dict[str, Any],
    principal: dict = Depends(current_principal),
):
    _require_admin(principal)

    backend = normalize_backend_def(payload)

    config = load_backends_config()
    if "backends" not in config or not isinstance(config["backends"], list):
        raise HTTPException(status_code=500, detail="Invalid backend config format")

    existing = {b.get("name") for b in config["backends"]}
    if backend["name"] in existing:
        raise HTTPException(status_code=409, detail="Backend name already exists")

    config["backends"].append(backend)
    save_backends_config(config)

    return {"ok": True, "backend": backend}


@app.get("/api/admin/embedding-models")
def list_embedding_models(principal: dict = Depends(current_principal)):
    _require_admin(principal)
    return {"models": EMBEDDING_MODELS, "default": DEFAULT_EMBEDDING_MODEL_ID}


@app.post("/api/admin/documents/upload")
async def upload_documents(
    principal: dict = Depends(current_principal),
    file: UploadFile = File(...),
    corpus_id: str = Form(...),
    embedding_model: str = Form(DEFAULT_EMBEDDING_MODEL_ID),
    chat_session_id: str = Form(...),
    user_id: Optional[str] = Form(None),
    chunk_size: int = Form(1200),
    chunk_overlap: int = Form(200),
):
    _require_admin(principal)

    model_ids = {m["id"] for m in EMBEDDING_MODELS}
    if embedding_model not in model_ids:
        raise HTTPException(400, "Unknown embedding model")

    if not corpus_id.strip():
        raise HTTPException(400, "Missing corpus_id")

    chat_session = CHAT_SESSIONS.get(chat_session_id)
    if not chat_session:
        raise HTTPException(400, "Chat not bootstrapped")

    mcp_client = chat_session.get("mcp")
    if not mcp_client:
        raise HTTPException(400, "Chat not bootstrapped")

    raw = await file.read()
    filename = Path(file.filename).name if file.filename else "upload"
    text = convert_upload_to_markdown(filename, raw)
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
    if not chunks:
        raise HTTPException(400, "No text content found")

    filename = Path(filename).name
    documents = []
    for idx, chunk in enumerate(chunks, start=1):
        documents.append({
            "id": f"{filename}-{idx}",
            "text": chunk,
            "source": filename,
            "source_type": (file.content_type or ""),
            "chunk_index": idx,
        })

    target_user_id = user_id or principal["sub"]

    result = await mcp_client.call_tool(
        "document_store.documents.upsert",
        {
            "user_id": target_user_id,
            "corpus_id": corpus_id,
            "embedding_model": embedding_model,
            "documents": documents,
        },
    )
    payload = extract_tool_payload(result)

    return {
        "ok": True,
        "corpus_id": corpus_id,
        "embedding_model": embedding_model,
        "chunks": len(documents),
        "result": result,
        "payload": payload,
    }


#######################################
### ---> Chat API                   ###
#######################################
@app.post("/api/chat/bootstrap")
async def chat_bootstrap(
    principal: dict = Depends(current_principal),
):
    username = principal["sub"]
    role = principal.get("role", "user")

    chat_session_id = secrets.token_urlsafe(16)

    client = MCPClient(user_id=username, role=role)
    await client.connect_to_server()

    tools = client.function_declarations

    CHAT_SESSIONS[chat_session_id] = {
        "user": username,
        "role": role,
        "mcp": client,
        "tools": tools,
    }

    tools_ui = []
    for tool in tools:  # tools is List[Tool]
        for fd in (tool.function_declarations or []):
            tools_ui.append({
                "name": fd.name,
                "description": getattr(fd, "description", "") or ""
            })

    return {"chat_session_id": chat_session_id, "tools_ui": tools_ui}


@app.post("/api/chat")
async def api_chat(
    payload: ChatIn,
    principal: dict = Depends(current_principal),
):
    username = principal["sub"]

    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")

    chat_session_id = payload.chat_session_id
    if not chat_session_id:
        raise HTTPException(status_code=400, detail="Missing chat_session_id")

    sess = CHAT_SESSIONS.get(chat_session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Unknown chat session")

    # ownership check (prevents guessing chat_session_id)
    if sess.get("user") != username:
        raise HTTPException(status_code=403, detail="Not your chat session")

    mcp_client = sess.get("mcp")
    if not mcp_client:
        raise HTTPException(status_code=400, detail="Chat not bootstrapped")

    all_tools = getattr(mcp_client, "function_declarations", None) or []

    selected = payload.selected_tools or []
    if selected:
        allowed = set(selected)
        tools_for_model = filter_tools(all_tools, allowed)
    else:
        tools_for_model = []

    system_instruction = None
    if payload.auto_search:
        corpus_id = (payload.corpus_id or "").strip()
        if not corpus_id:
            raise HTTPException(status_code=400, detail="Missing corpus_id for auto search")

        model_ids = {m["id"] for m in EMBEDDING_MODELS}
        embedding_model = payload.embedding_model or DEFAULT_EMBEDDING_MODEL_ID
        if embedding_model not in model_ids:
            raise HTTPException(status_code=400, detail="Unknown embedding model")

        search_k = payload.search_k or 5
        search_result = await mcp_client.call_tool(
            "document_store.documents.search",
            {
                "user_id": username,
                "corpus_id": corpus_id,
                "embedding_model": embedding_model,
                "query": msg,
                "k": search_k,
            },
        )
        payload_data = extract_tool_payload(search_result)
        system_instruction = build_retrieval_instruction(payload_data)

    text = await mcp_client.process_query(
        query=msg,
        enabled_tools=tools_for_model,
        system_instruction=system_instruction,
    )
    return {"text": text}
