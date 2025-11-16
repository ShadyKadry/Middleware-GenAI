# middleware/main.py

from fastapi import FastAPI
from mcp_manager.router import router as mcp_router

app = FastAPI()

app.include_router(mcp_router, prefix="/mcp")

@app.get("/")
def read_root():
    return {"message": "GenAI Middleware API is running"}

