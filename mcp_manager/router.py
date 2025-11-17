# middleware/mcp_manager/router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

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

