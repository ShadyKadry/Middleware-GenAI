import logging
import secrets
import sys
from pathlib import Path
from typing import List, Any, Dict, Optional, Set

from fastapi import (
    FastAPI,
    Request,
    Form,
    HTTPException,
    Depends,
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

    text = await mcp_client.process_query(query=msg, enabled_tools=tools_for_model)
    return {"text": text}
