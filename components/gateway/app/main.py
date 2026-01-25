import json
import logging
import secrets
import sys
from pathlib import Path
from typing import List, Any, Dict, Optional

from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.genai.types import Tool
from itsdangerous import URLSafeSerializer, BadSignature
from passlib.context import CryptContext
from pydantic import BaseModel

from ..app.mcp_client import MCPClient

# gateway project root
BASE_DIR = Path(__file__).resolve().parent.parent

# create logger
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     handlers=[
#         logging.StreamHandler(sys.stderr),  # <-- critical for STDIO MCP
#     ],
#     force=True,
# )
# logger = logging.getLogger(__name__)


###############################################
### ---> Login related functionality/data   ### TODO
###############################################
SECRET_KEY = "dev-change-me"
COOKIE_NAME = "session"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
signer = URLSafeSerializer(SECRET_KEY, salt="session")

# todo: implement real user creation and remove USERS and ROLES from visible code base (move to DB -> dedicated file in DB for user credentials?! Or other approach more fitting?)
USERS = {
    "user": pwd_context.hash("userpass"),
    "arno": pwd_context.hash("arnopass"),
    "shady": pwd_context.hash("shadypass"),
    "george": pwd_context.hash("georgepass"),
    "bach": pwd_context.hash("bachpass"),
}
ROLES = {
    "user":"admin",
    "arno": "admin",
    "shady": "admin",
    "george": "admin",
    "bach": "user"
}

# embedding models exposed in the admin UI
EMBEDDING_MODELS = [
    {"id": "gemini-embedding-001", "label": "Gemini embedding-001"},
    {"id": "stub-256", "label": "Stub (deterministic, 256d)"},
]
DEFAULT_EMBEDDING_MODEL_ID = "gemini-embedding-001"

# todo: where should ongoing sessions be saved? DB? in code is suboptimal security-wise...
CHAT_SESSIONS: Dict[str, Dict[str, Any]] = {}

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


def filter_tools(all_tools, allowed_names: set[str]):
    filtered = []
    for tool in all_tools:
        fds = getattr(tool, "function_declarations", None) or []
        # keep only declarations whose name is allowed
        kept = [fd for fd in fds if fd.name in allowed_names]
        if kept:
            # rebuild Tool with only kept declarations
            filtered.append(Tool(function_declarations=kept))
    return filtered


def get_session_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)  # fixme remove cookie based access
    if not token:
        return None
    try:
        return signer.loads(token)
    except BadSignature:
        return None


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

@app.get("/")
def login_page(request: Request):
    session = get_session_user(request)
    if session:
        return RedirectResponse("/app", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


# todo: currently done via cookies. implement proper log-in
@app.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username not in USERS:
        raise HTTPException(401, "Not allowed")
    if not pwd_context.verify(password, USERS[username]):
        raise HTTPException(401, "Wrong password")

    session = {"user": username, "role": ROLES.get(username, "user")}
    token = signer.dumps(session)

    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 12,
    )
    return resp


@app.post("/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.get("/api/me")
def me(request: Request):
    session = get_session_user(request)
    if not session:
        raise HTTPException(401)
    return session


@app.get("/api/admin/embedding-models")
def list_embedding_models(request: Request):
    session = get_session_user(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(403, "Not allowed")
    return {"models": EMBEDDING_MODELS, "default": DEFAULT_EMBEDDING_MODEL_ID}


@app.post("/api/admin/documents/upload")
async def upload_documents(
    request: Request,
    file: UploadFile = File(...),
    corpus_id: str = Form(...),
    embedding_model: str = Form(DEFAULT_EMBEDDING_MODEL_ID),
    chat_session_id: str = Form(...),
    user_id: Optional[str] = Form(None),
    chunk_size: int = Form(1200),
    chunk_overlap: int = Form(200),
):
    session = get_session_user(request)
    if not session or session.get("role") != "admin":
        raise HTTPException(403, "Not allowed")

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
    if not raw:
        raise HTTPException(400, "Empty file")

    text = raw.decode("utf-8", errors="replace")
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
    if not chunks:
        raise HTTPException(400, "No text content found")

    filename = Path(file.filename).name if file.filename else "upload.txt"
    documents = []
    for idx, chunk in enumerate(chunks, start=1):
        documents.append({
            "id": f"{filename}-{idx}",
            "text": chunk,
            "source": filename,
            "chunk_index": idx,
        })

    target_user_id = user_id or session["user"]

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




@app.get("/app")
def app_page(request: Request):
    session = get_session_user(request)
    if not session:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "app.html",
        {
            "request": request,
            "user": session["user"],
        },
    )

@app.post("/api/chat")
async def api_chat(payload: ChatIn, request: Request):
    #logger.debug(f"Starts processing request with {payload.selected_tools} tools enabled/selected.")
    user_credentials = get_session_user(request)
    #logger.debug(f"Credentials of requester: {user_credentials}")
    #logger.debug(f"Session key: {CHAT_SESSIONS[payload.chat_session_id]}")

    if not user_credentials:
        raise HTTPException(status_code=401, detail="Not logged in")

    msg = payload.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")

    mcp_client = CHAT_SESSIONS[payload.chat_session_id].get("mcp")
    if not mcp_client:
        raise HTTPException(status_code=400, detail="Chat not bootstrapped")

    # tools from bootstrap (MCP->Gemini converted Tool objects)
    all_tools = getattr(mcp_client, "function_declarations", None) or []

    selected = payload.selected_tools or []
    if selected:
        allowed = set(selected)
        tools_for_model = filter_tools(all_tools, allowed)

        tool_names = [tool.function_declarations[0].name for tool in tools_for_model]
        #logger.debug(f"Available MCP tools are: {tool_names}")
    else:
        tool_names, tools_for_model = [], []

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
                "user_id": user_credentials["user"],
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


@app.post("/api/chat/bootstrap")
async def chat_bootstrap(request: Request):
    sess = get_session_user(request)
    if not sess:
        raise HTTPException(401, "Not logged in")

    username = sess["user"]
    role = sess.get("role", "user")

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
