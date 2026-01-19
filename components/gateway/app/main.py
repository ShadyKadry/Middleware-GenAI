import secrets
from pathlib import Path
from typing import List, Any, Dict, Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.genai.types import Tool
from itsdangerous import URLSafeSerializer, BadSignature
from passlib.context import CryptContext
from pydantic import BaseModel

from ..app.mcp_client import MCPClient

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
    selected_tools: Optional[List[str]] = None
    chat_session_id: Optional[str] = None


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


@app.post("/api/chat")
async def api_chat(payload: ChatIn, request: Request):
    session = get_session_user(request)
    print(f"Session: {session}")
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")

    msg = payload.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Empty message")
    #print(CHAT_SESSIONS[payload.chat_session_id])
    mcp_client = CHAT_SESSIONS[payload.chat_session_id].get("mcp")
    if not mcp_client:
        raise HTTPException(status_code=400, detail="Chat not bootstrapped")

    # tools from bootstrap (your MCP->Gemini converted Tool objects)
    all_tools = getattr(mcp_client, "function_declarations", None) or []

    selected = payload.selected_tools or []
    if selected:
        allowed = set(selected)
        tools_for_model = filter_tools(all_tools, allowed)

        tool_names = [tool.function_declarations[0].name for tool in tools_for_model]
        print(tool_names)
    else:
        tool_names = []
    print("Total available tools: ", len(tool_names))

    # resp = mcp_client.models.generate_content(
    #     model="gemini-2.5-flash",
    #     contents=msg,
    #     config=types.GenerateContentConfig(tools=tools_for_model),
    # )

    return {"text": "placeholder"} # resp.text}


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
