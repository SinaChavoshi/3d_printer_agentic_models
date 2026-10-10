# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""FastAPI server for the 3D Printer Agentic Studio."""

import asyncio
import hmac
import json
import os
import time
import uuid
from collections import OrderedDict
from threading import Lock

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:  # Optional: pick up settings from a local .env file before other modules read them.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app.cad_agent import CadGenerationError, generate_cad_model

app = FastAPI(
    title="3D Printer Agentic Studio",
    description="LLM-powered parametric 3D CAD generation (Gemini, Claude, GPT, Grok, DeepSeek, Kimi, self-hosted).",
    version="3.1.0",
)

# The studio UI is served from this same origin, so CORS is off by default.
# Set CORS_ALLOW_ORIGINS="https://a.example,https://b.example" to allow others.
_cors_origins = [
    o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key", "X-Studio-Token"],
    )


def require_access_token(x_studio_token: str | None = Header(default=None)) -> None:
    """If STUDIO_ACCESS_TOKEN is set, every API call must send it in X-Studio-Token."""
    expected = os.getenv("STUDIO_ACCESS_TOKEN")
    if expected and not (
        x_studio_token and hmac.compare_digest(x_studio_token, expected)
    ):
        raise HTTPException(
            status_code=401, detail="Missing or invalid X-Studio-Token."
        )


class SessionStore:
    """Small thread-safe LRU cache of generated STLs with a time-to-live."""

    def __init__(self, max_items: int, ttl_seconds: int):
        self._items: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._max_items = max_items
        self._ttl = ttl_seconds
        self._lock = Lock()

    def put(self, value: dict) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._items[session_id] = (time.monotonic(), value)
            while len(self._items) > self._max_items:
                self._items.popitem(last=False)
        return session_id

    def get(self, session_id: str) -> dict | None:
        with self._lock:
            item = self._items.get(session_id)
            if item is None:
                return None
            created, value = item
            if time.monotonic() - created > self._ttl:
                del self._items[session_id]
                return None
            return value


SESSION_STORE = SessionStore(
    max_items=int(os.getenv("SESSION_STORE_MAX_ITEMS", "50")),
    ttl_seconds=int(os.getenv("SESSION_STORE_TTL_SECONDS", "3600")),
)


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    current_code: str | None = Field(default=None, max_length=100_000)
    model_name: str = Field(default="gemini-2.5-pro", max_length=100)
    api_key: str | None = Field(default=None, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)
    provider: str = Field(default="google", max_length=50)
    enable_vlm_refinement: bool = True


MODELS = [
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (default)", "provider": "google"},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (fast)", "provider": "google"},
    {
        "id": "gemini-3.0-pro",
        "name": "Gemini 3.0 Pro (falls back to 2.5 Pro if unavailable)",
        "provider": "google",
    },
    {
        "id": "gemini-3.5-flash",
        "name": "Gemini 3.5 Flash (falls back to 2.5 Pro if unavailable)",
        "provider": "google",
    },
    {"id": "claude-opus-4-7", "name": "Claude Opus 4.7", "provider": "anthropic"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "anthropic"},
    {
        "id": "claude-3-7-sonnet-20250219",
        "name": "Claude 3.7 Sonnet",
        "provider": "anthropic",
    },
    {"id": "grok-4.20-reasoning", "name": "Grok 4.20 Reasoning", "provider": "xai"},
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
    {"id": "o3-mini", "name": "o3-mini", "provider": "openai"},
    {
        "id": "deepseek-chat",
        "name": "DeepSeek V3 (deepseek-chat)",
        "provider": "deepseek",
    },
    {
        "id": "deepseek-reasoner",
        "name": "DeepSeek R1 (deepseek-reasoner)",
        "provider": "deepseek",
    },
    {"id": "moonshot-v1-8k", "name": "Kimi / Moonshot v1 8K", "provider": "kimi"},
    {
        "id": "qwen2.5-coder",
        "name": "Qwen 2.5 Coder (self-hosted / Ollama)",
        "provider": "self-hosted",
    },
]
PROVIDER_NAMES = [
    {"id": "google", "name": "Google Gemini (Vertex AI / API key)"},
    {"id": "anthropic", "name": "Anthropic Claude (API key)"},
    {"id": "xai", "name": "xAI Grok (API key)"},
    {"id": "openai", "name": "OpenAI (API key)"},
    {"id": "deepseek", "name": "DeepSeek (API key)"},
    {"id": "kimi", "name": "Kimi / Moonshot (API key)"},
    {"id": "self-hosted", "name": "Self-hosted (Ollama, vLLM; LLM_BASE_URL)"},
]


@app.get("/api/models")
def list_available_models():
    """Lists selectable providers and models."""
    return {"providers": PROVIDER_NAMES, "models": MODELS}


def _run_generation(
    req: GenerationRequest, client_key: str | None, log_callback=None
) -> dict:
    return generate_cad_model(
        prompt=req.prompt,
        current_code=req.current_code,
        model_name=req.model_name,
        api_key=req.api_key or client_key,
        base_url=req.base_url,
        provider=req.provider,
        enable_vlm_refinement=req.enable_vlm_refinement,
        log_callback=log_callback,
    )


def _store_and_describe(req: GenerationRequest, result: dict) -> dict:
    session_id = SESSION_STORE.put(
        {"stl_bytes": result["stl_bytes"], "prompt": req.prompt}
    )
    return {
        "session_id": session_id,
        "code": result["code"],
        "explanation": result["explanation"],
        "log": result["log"],
        "stats": result["stats"],
        "obj_data": result["obj_data"],
    }


@app.post("/api/generate", dependencies=[Depends(require_access_token)])
def generate_mesh(
    req: GenerationRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Generates or iteratively modifies a 3D model and returns the mesh."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")
    try:
        result = _run_generation(req, x_api_key)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except CadGenerationError as err:
        raise HTTPException(
            status_code=502, detail={"message": str(err), "log": err.log}
        ) from err
    return _store_and_describe(req, result)


@app.post("/api/generate_stream", dependencies=[Depends(require_access_token)])
async def generate_mesh_stream(
    req: GenerationRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Server-Sent Events stream of progress logs, then a 'complete' or 'error' event."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    async def event_generator():
        loop = asyncio.get_running_loop()
        log_queue: asyncio.Queue[str] = asyncio.Queue()

        def queue_log(msg: str) -> None:
            # Called from the worker thread; hand off to the event loop safely.
            loop.call_soon_threadsafe(log_queue.put_nowait, msg)

        task = loop.run_in_executor(
            None, lambda: _run_generation(req, x_api_key, queue_log)
        )

        while not task.done() or not log_queue.empty():
            try:
                msg = await asyncio.wait_for(log_queue.get(), timeout=0.2)
                yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
            except TimeoutError:
                yield ": keep-alive\n\n"

        try:
            result = await task
        except (ValueError, CadGenerationError) as err:
            payload = {
                "type": "error",
                "message": str(err),
                "log": getattr(err, "log", ""),
            }
            yield f"data: {json.dumps(payload)}\n\n"
            return
        except Exception as err:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Unexpected server error: {err}'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'complete', **_store_and_describe(req, result)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/export/{session_id}/stl", dependencies=[Depends(require_access_token)])
def download_stl(session_id: str):
    """Downloads a generated model as a binary STL."""
    session = SESSION_STORE.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return Response(
        content=session["stl_bytes"],
        media_type="application/sla",
        headers={
            "Content-Disposition": f"attachment; filename=model_{session_id[:8]}.stl"
        },
    )


STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def read_root():
    """Serves the studio UI."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse(
        "<h2>3D Printer Agentic Studio backend is running (static/ not found).</h2>"
    )


if __name__ == "__main__":
    import uvicorn

    # Local-only by default; generated code and API keys should not be exposed to the network.
    uvicorn.run(
        app, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8088"))
    )
