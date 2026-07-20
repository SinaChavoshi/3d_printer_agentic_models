# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import os
import uuid
from fastapi import FastAPI, HTTPException, Response
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

@app.get("/api/models")
def list_available_models():
    """List verified active Vertex AI Gemini models."""
    return {
        "models": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (Fast & Recommended)"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (Complex CAD & High Precision)"},
        ]
    }

@app.post("/api/generate")
def generate_mesh(req: GenerationRequest):
    """Generates or iteratively modifies a 3D model code & renders mesh."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt string cannot be empty.")
    
    result = generate_cad_model(
        prompt=req.prompt,
        current_code=req.current_code,
        model_name=req.model_name,
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
