# middleware/mcp_manager/router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

from content_manager import create_document, get_document
from embedding_manager import embed_document, search_similar


router = APIRouter()
tool_registry = {}

class ToolRegistration(BaseModel):
    name: str
    description: str
    url: str

class ToolInvocation(BaseModel):
    tool_name: str
    jsonrpc_payload: dict

class RegistrationResponse(BaseModel):
    message: str

@router.post("/register_tool", response_model=RegistrationResponse)
def register_tool(tool: ToolRegistration):
    if tool.name in tool_registry:
        raise HTTPException(status_code=400, detail="Tool already registered.")
    tool_registry[tool.name] = tool
    return {"message": f"{tool.name} registered."}

@router.get("/tools")
def list_tools():
    return list(tool_registry.values())

@router.post("/invoke_tool")
def invoke_tool(payload: ToolInvocation):
    tool = tool_registry.get(payload.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found.")
    try:
        response = httpx.post(tool.url, json=payload.jsonrpc_payload)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- Document management endpoints (backed by Postgres) ----

class DocumentCreate(BaseModel):
    title: str
    content: str

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/docs")
def create_doc(doc: DocumentCreate):
    doc_id = create_document(doc.title, doc.content)
    return {"id": doc_id, "title": doc.title}


@router.get("/docs/{doc_id}")
def get_doc(doc_id: int):
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc

@router.post("/docs/{doc_id}/embed")
def embed_doc(doc_id: int):
    try:
        embed_document(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok", "document_id": doc_id}

@router.post("/search")
def search(req: SearchRequest):
    results = search_similar(req.query, req.top_k)
    return {"results": results}

