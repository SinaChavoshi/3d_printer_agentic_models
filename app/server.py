# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import os
import uuid
from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from app.cad_agent import generate_cad_model

app = FastAPI(
    title="3D Printer Agentic Models Studio",
    description="LLM-Powered 3D Parametric CAD Generation and In-Browser 3D Visualizer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE: dict[str, dict] = {}

class GenerationRequest(BaseModel):
    prompt: str
    current_code: str | None = None
    model_name: str = "gemini-2.5-flash"
    api_key: str | None = None
    base_url: str | None = None
    provider: str = "google"

@app.get("/api/models")
def list_available_models():
    """List selectable LLM AI models and providers."""
    return {
        "providers": [
            {"id": "google", "name": "Google Gemini (Vertex AI / API Key)"},
            {"id": "openai", "name": "OpenAI (GPT-4o / GPT-4o-mini)"},
            {"id": "self-hosted", "name": "Self-Hosted / Local LLM (Ollama, vLLM, LM Studio)"},
        ],
        "models": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (Fast & Recommended)"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (Complex CAD & High Precision)"},
            {"id": "gpt-4o", "name": "OpenAI GPT-4o"},
            {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o mini"},
            {"id": "qwen2.5-coder", "name": "Qwen 2.5 Coder (Self-Hosted / Ollama)"},
        ]
    }

@app.post("/api/generate")
def generate_mesh(
    req: GenerationRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Generates or iteratively modifies a 3D model code & renders mesh."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt string cannot be empty.")
    
    # Allow API Key from header or request body
    user_api_key = req.api_key or x_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    result = generate_cad_model(
        prompt=req.prompt,
        current_code=req.current_code,
        model_name=req.model_name,
        api_key=user_api_key,
        base_url=req.base_url or os.getenv("LLM_BASE_URL"),
        provider=req.provider or os.getenv("LLM_PROVIDER", "google"),
    )
    
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        "stl_bytes": result["stl_bytes"],
        "code": result["code"],
        "prompt": req.prompt,
    }
    
    return {
        "session_id": session_id,
        "code": result["code"],
        "explanation": result["explanation"],
        "log": result["log"],
        "stats": result["stats"],
        "obj_data": result["obj_data"],
    }

@app.get("/api/export/{session_id}/stl")
def download_stl(session_id: str):
    """Download generated 3D model as STL file ready for 3D printing."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Session or STL file not found.")
    
    stl_bytes = SESSION_STORE[session_id]["stl_bytes"]
    return Response(
        content=stl_bytes,
        media_type="application/sla",
        headers={
            "Content-Disposition": f"attachment; filename=model_{session_id[:8]}.stl"
        },
    )

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    """Serves the 3D Visualizer Studio UI."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h2>3D Printer Agentic Studio Backend Running</h2>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
