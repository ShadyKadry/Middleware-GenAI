import secrets
from asyncio.subprocess import Process
from pathlib import Path
from typing import List, Any, Dict

import httpx
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from mcp import ClientSession, StdioServerParameters, stdio_client
from passlib.context import CryptContext
from itsdangerous import URLSafeSerializer, BadSignature
import os
from pydantic import BaseModel

from ..app.mcp_client import MCPClient
from components.gateway.app.mcp_process import McpProcess

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI()

templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)
# --- config ---
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

# todo: where should ongoing sessions be saved?
CHAT_SESSIONS: Dict[str, Dict[str, Any]] = {}


def get_session_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)  # fixme remove cookie based access
    if not token:
        return None
    try:
        return signer.loads(token)
    except BadSignature:
        return None


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


class ChatIn(BaseModel):
    message: str

@app.post("/api/chat")
def api_chat(payload: ChatIn, request: Request):
    session = get_session_user(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")

    msg = payload.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")

    # Gemini 2.5 Flash model id (as used by providers/docs)
    client = CHAT_SESSIONS[session].get("mcp")
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=msg,
    )
    return {"text": "That's where the answer will be displayed. Coming soon." or resp.text}

class ToolUI(BaseModel):
    name: str
    description: str = ""

class BootstrapOut(BaseModel):
    chat_session_id: str
    tools_ui: List[ToolUI]



@app.post("/api/chat/bootstrap")
async def chat_bootstrap(request: Request):
    sess = get_session_user(request)
    if not sess:
        raise HTTPException(401, "Not logged in")

    username = sess["user"]
    role = sess.get("role", "user")

    chat_session_id = secrets.token_urlsafe(16)

    # start per-session MCP process
    # mcp_proc = await McpProcess.start(username=username, role=role)

    client = MCPClient(user_id=username, role=role)
    await client.connect_to_server()

    tools = client.function_declarations

    CHAT_SESSIONS[chat_session_id] = {
        "user": username,
        "role": role,
        "mcp": client,
        "tools": tools,
    }

    #tools_ui = [{"name": t["name"], "description": t.get("description","")} for t in tools]
    tools_ui = []
    for tool in tools:  # tools is List[Tool]
        for fd in (tool.function_declarations or []):
            tools_ui.append({
                "name": fd.name,
                "description": getattr(fd, "description", "") or ""
            })
    return {"chat_session_id": chat_session_id, "tools_ui": tools_ui}

# @app.post("/api/chat/bootstrap", response_model=BootstrapOut)
# def chat_bootstrap(request: Request):
#     sess = get_session_user(request)
#     if not sess:
#         raise HTTPException(status_code=401, detail="Not logged in")
#
#     username = sess["user"]
#     role = sess.get("role", "user")
#
#     # 1) handshake / list tools from MCP
#     tools = mcp_rpc("list_tools", {"username": username, "role": role})
#
#     # Expecting tools to be a list of {name, description, inputSchema, ...}
#     if not isinstance(tools, list):
#         raise HTTPException(status_code=502, detail="MCP list_tools returned unexpected shape")
#
#     # 2) create chat session and store full tool schemas
#     chat_session_id = secrets.token_urlsafe(16)
#
#     CHAT_SESSIONS[chat_session_id] = {
#         "user": username,
#         "role": role,
#         "tools": tools,  # full MCP tool definitions (schemas)
#         "enabled_tools": [t.get("name") for t in tools if isinstance(t, dict) and t.get("name")],
#     }
#
#     tools_ui = [
#         ToolUI(name=t.get("name", "unnamed"), description=t.get("description", "") or "")
#         for t in tools
#         if isinstance(t, dict)
#     ]
#
#     return BootstrapOut(chat_session_id=chat_session_id, tools_ui=tools_ui)

# def mcp_rpc(method: str, params: dict) -> Any:
#     payload = {
#         "jsonrpc": "2.0",
#         "id": secrets.token_hex(8),
#         "method": method,
#         "params": params,
#     }
#     try:
#         r = httpx.post(MCP_RPC_URL, json=payload, timeout=15.0)
#         r.raise_for_status()
#         data = r.json()
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"MCP request failed: {e}")
#
#     if "error" in data:
#         raise HTTPException(status_code=502, detail=f"MCP error: {data['error']}")
#     return data.get("result")


#python middleware.py --user arno --role admin