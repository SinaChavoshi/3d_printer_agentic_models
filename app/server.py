# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import json
import os
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel

from app.cad_agent import generate_cad_model

app = FastAPI(
    title="3D Printer Agentic Models Studio v2.5",
    description="LLM VLM-Powered 3D Parametric CAD Generation with Multi-Provider Support (Gemini 2.5 Pro, Claude 3.7, OpenAI, DeepSeek, Kimi)",
    version="2.5.0",
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
    model_name: str = "gemini-2.5-pro"
    api_key: str | None = None
    base_url: str | None = None
    provider: str = "google"
    enable_vlm_refinement: bool = True

@app.get("/api/models")
def list_available_models():
    """List selectable LLM AI models and providers."""
    return {
        "providers": [
            {"id": "google", "name": "Google Gemini (Vertex AI / API Key)"},
            {"id": "anthropic", "name": "Anthropic Claude (API Key)"},
            {"id": "openai", "name": "OpenAI (API Key)"},
            {"id": "deepseek", "name": "DeepSeek AI (V3 / R1)"},
            {"id": "kimi", "name": "Kimi / Moonshot AI"},
            {"id": "self-hosted", "name": "Self-Hosted / Local LLM (Ollama, vLLM)"},
        ],
        "models": [
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (Vertex AI - Default Main Demo)", "provider": "google"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (Vertex AI - Fast VLM)", "provider": "google"},
            {"id": "claude-3-7-sonnet-20250219", "name": "Anthropic Claude 3.7 Sonnet", "provider": "anthropic"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Anthropic Claude 3.5 Sonnet", "provider": "anthropic"},
            {"id": "gpt-4o", "name": "OpenAI GPT-4o", "provider": "openai"},
            {"id": "o3-mini", "name": "OpenAI o3-mini", "provider": "openai"},
            {"id": "deepseek-chat", "name": "DeepSeek V3 (deepseek-chat)", "provider": "deepseek"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (deepseek-reasoner)", "provider": "deepseek"},
            {"id": "moonshot-v1-8k", "name": "Kimi / Moonshot v1 8K", "provider": "kimi"},
            {"id": "qwen2.5-coder", "name": "Qwen 2.5 Coder (Self-Hosted / Ollama)", "provider": "self-hosted"},
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
    
    user_api_key = req.api_key or x_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    result = generate_cad_model(
        prompt=req.prompt,
        current_code=req.current_code,
        model_name=req.model_name,
        api_key=user_api_key,
        base_url=req.base_url or os.getenv("LLM_BASE_URL"),
        provider=req.provider or os.getenv("LLM_PROVIDER", "google"),
        enable_vlm_refinement=req.enable_vlm_refinement,
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

@app.post("/api/generate_stream")
async def generate_mesh_stream(
    req: GenerationRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Streaming endpoint yielding real-time action logs via Server-Sent Events (SSE)."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt string cannot be empty.")

    user_api_key = req.api_key or x_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    async def event_generator():
        log_queue = asyncio.Queue()

        def queue_log(msg: str):
            log_queue.put_nowait(msg)

        loop = asyncio.get_running_loop()

        def run_cad():
            return generate_cad_model(
                prompt=req.prompt,
                current_code=req.current_code,
                model_name=req.model_name,
                api_key=user_api_key,
                base_url=req.base_url or os.getenv("LLM_BASE_URL"),
                provider=req.provider or os.getenv("LLM_PROVIDER", "google"),
                enable_vlm_refinement=req.enable_vlm_refinement,
                log_callback=queue_log,
            )

        task = loop.run_in_executor(None, run_cad)

        while not task.done() or not log_queue.empty():
            try:
                msg = await asyncio.wait_for(log_queue.get(), timeout=0.2)
                yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

        result = await task

        session_id = str(uuid.uuid4())
        SESSION_STORE[session_id] = {
            "stl_bytes": result["stl_bytes"],
            "code": result["code"],
            "prompt": req.prompt,
        }

        payload = {
            "type": "complete",
            "session_id": session_id,
            "code": result["code"],
            "explanation": result["explanation"],
            "log": result["log"],
            "stats": result["stats"],
            "obj_data": result["obj_data"],
        }
        yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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
