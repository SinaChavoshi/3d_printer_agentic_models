# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""Multi-provider LLM CAD agent: generate, auto-fix, and visually refine models."""

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import google.auth
import httpx
import trimesh
from google.genai import client, types

from app.mesh_engine import (
    execute_python_3d_code,
    export_mesh_data,
    render_mesh_snapshots,
)

SYSTEM_INSTRUCTION = """
You are an expert 3D CAD modeling AI assistant that generates 3D printable objects using Python's `trimesh` library.

YOUR TASK:
Write clean, valid, executable Python code that creates a 3D model assigned to a single variable named `mesh` (of type `trimesh.Trimesh`).

CRITICAL ITERATIVE MODIFICATION RULES:
1. When `Existing Python Code to Modify` is provided:
   - YOU MUST MODIFY, EXTEND, AND EDIT THE EXISTING CODE.
   - Do NOT discard the existing design or rewrite it from scratch unless the user explicitly asks to start over.
   - Keep existing shapes, dimensions, and features intact, and apply the user's requested additions, subtractions, holes, or modifications directly to the existing `mesh`.
2. Always assign the final 3D model object to a variable named `mesh`.
3. Only these modules are available (and already imported): `trimesh`, `np` (numpy), `math`. Do not import anything else. File, network, and OS access are not available.
4. Standard 3D geometry builders:
   - Boxes: `trimesh.creation.box(extents=[w, l, h])`
   - Cylinders: `trimesh.creation.cylinder(radius=r, height=h, sections=32)`
   - Spheres: `trimesh.creation.icosphere(subdivisions=3, radius=r)`
   - Cones: `trimesh.creation.cone(radius=r, height=h, sections=32)`
   - Hollow Tubes/Annulus: `trimesh.creation.annulus(r_min=r1, r_max=r2, height=h, sections=32)`
5. Boolean CSG Operations & Transformations:
   - `mesh1.difference(mesh2, engine='manifold')` (Subtractions/Holes)
   - `mesh1.union(mesh2, engine='manifold')` (Unions)
   - `mesh.apply_translation([x, y, z])`
   - `mesh.apply_transform(trimesh.transformations.rotation_matrix(angle, [0, 0, 1]))`
   - `mesh.apply_scale(s)`
6. OUTPUT FORMAT:
   Return ONLY valid Python code inside a markdown python block:
   ```python
   # Python CAD code here
   mesh = ...
   ```
"""

DEFAULT_GOOGLE_MODEL = "gemini-2.5-pro"
MAX_FIX_ATTEMPTS = 2
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))


@dataclass(frozen=True)
class ProviderConfig:
    """Static description of an LLM provider."""

    key_env: tuple[str, ...]
    default_base_url: str | None = None
    base_url_env: str | None = None
    openai_compatible: bool = True


PROVIDERS: dict[str, ProviderConfig] = {
    "google": ProviderConfig(
        key_env=("GEMINI_API_KEY", "GOOGLE_API_KEY"), openai_compatible=False
    ),
    "anthropic": ProviderConfig(
        key_env=("ANTHROPIC_API_KEY",), openai_compatible=False
    ),
    "openai": ProviderConfig(
        key_env=("OPENAI_API_KEY",), default_base_url="https://api.openai.com/v1"
    ),
    "xai": ProviderConfig(
        key_env=("XAI_API_KEY",), default_base_url="https://api.x.ai/v1"
    ),
    "deepseek": ProviderConfig(
        key_env=("DEEPSEEK_API_KEY",), default_base_url="https://api.deepseek.com/v1"
    ),
    "kimi": ProviderConfig(
        key_env=("MOONSHOT_API_KEY",), default_base_url="https://api.moonshot.cn/v1"
    ),
    "self-hosted": ProviderConfig(
        key_env=("LLM_API_KEY",),
        default_base_url="http://localhost:11434/v1",
        base_url_env="LLM_BASE_URL",
    ),
}
PROVIDER_ALIASES = {"moonshot": "kimi", "local": "self-hosted", "grok": "xai"}


class CadGenerationError(Exception):
    """Raised when a model could not be generated; carries the action log."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


def normalize_provider(provider: str | None) -> str:
    """Returns the canonical provider id or raises ValueError."""
    prov = (provider or "google").lower().strip()
    prov = PROVIDER_ALIASES.get(prov, prov)
    if prov not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Supported: {', '.join(PROVIDERS)}."
        )
    return prov


def _allowed_base_urls() -> set[str]:
    raw = os.getenv("LLM_ALLOWED_BASE_URLS", "")
    return {u.strip().rstrip("/") for u in raw.split(",") if u.strip()}


def resolve_base_url(provider: str, requested: str | None) -> str | None:
    """Returns the endpoint to call for an OpenAI-compatible provider.

    Client-supplied URLs are only honoured if the server operator listed them in
    LLM_ALLOWED_BASE_URLS, so requests can never redirect calls (and keys) to an
    arbitrary host.
    """
    cfg = PROVIDERS[provider]
    if not cfg.openai_compatible:
        if requested:
            raise ValueError(
                f"Provider '{provider}' does not accept a custom base URL."
            )
        return None
    configured = os.getenv(cfg.base_url_env) if cfg.base_url_env else None
    default = (configured or cfg.default_base_url or "").rstrip("/")
    if not requested or requested.strip().rstrip("/") == default:
        return default
    candidate = requested.strip().rstrip("/")
    if candidate in _allowed_base_urls():
        return candidate
    raise ValueError(
        "Custom base URL is not allowed. Ask the server operator to add it to "
        "LLM_ALLOWED_BASE_URLS (or set LLM_BASE_URL for self-hosted models)."
    )


def resolve_api_key(provider: str, client_key: str | None) -> str | None:
    """Client-supplied key wins; otherwise only this provider's own env vars."""
    if client_key and client_key.strip():
        return client_key.strip()
    for env_name in PROVIDERS[provider].key_env:
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()
    return None


def extract_python_code(llm_response_text: str) -> str | None:
    """Extracts the first fenced code block, or None if there is none."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", llm_response_text, re.DOTALL)
    return match.group(1).strip() if match else None


def get_genai_client(api_key: str | None = None) -> client.Client:
    """Gemini client using an API key, or Vertex AI via Application Default Credentials."""
    if api_key:
        return client.Client(api_key=api_key)
    try:
        _, adc_project = google.auth.default()
    except Exception:
        adc_project = None
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or adc_project
    if not project_id:
        raise CadGenerationError(
            "No Gemini credentials: set GEMINI_API_KEY, or configure Application Default "
            "Credentials and GOOGLE_CLOUD_PROJECT for Vertex AI."
        )
    region = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    return client.Client(vertexai=True, project=project_id, location=region)


def query_anthropic_llm(prompt: str, api_key: str | None, model_name: str) -> str:
    """Queries the Anthropic Messages API."""
    if not api_key:
        raise CadGenerationError(
            "Anthropic API key is required. Set ANTHROPIC_API_KEY or enter a key in Settings."
        )
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model_name,
        "max_tokens": 4096,
        "system": SYSTEM_INSTRUCTION,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as http_client:
        resp = http_client.post(
            "https://api.anthropic.com/v1/messages", json=payload, headers=headers
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


def query_openai_compatible_llm(
    prompt: str, base_url: str, api_key: str | None, model_name: str
) -> str:
    """Queries an OpenAI-compatible chat completions endpoint."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    with httpx.Client(timeout=LLM_TIMEOUT_SECONDS) as http_client:
        resp = http_client.post(
            base_url.rstrip("/") + "/chat/completions", json=payload, headers=headers
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _build_fix_prompt(user_request: str, failing_code: str, error_text: str) -> str:
    return (
        f"The user asked for: {user_request}\n\n"
        f"This code was generated for that request:\n```python\n{failing_code}\n```\n\n"
        f"Running it failed with:\n```\n{error_text[-4000:]}\n```\n\n"
        "Fix the code so it runs and still satisfies the request. Keep the design intact. "
        "Return the complete corrected code assigning the result to `mesh`."
    )


def generate_cad_model(
    prompt: str,
    current_code: str | None = None,
    model_name: str = DEFAULT_GOOGLE_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
    provider: str = "google",
    enable_vlm_refinement: bool = True,
    log_callback: Callable[[str], Any] | None = None,
) -> dict:
    """Generates (or modifies) a CAD model with the selected LLM provider.

    Raises:
        ValueError: invalid provider or base URL (client error).
        CadGenerationError: the LLM call or code execution failed.
    """
    events: list[str] = []

    def emit_log(msg: str) -> None:
        events.append(msg)
        if log_callback:
            log_callback(msg)

    prov = normalize_provider(provider)
    endpoint = resolve_base_url(prov, base_url)
    key = resolve_api_key(prov, api_key)
    used_model = model_name

    emit_log(f"🚀 Generating CAD model for: '{prompt}'")
    emit_log(f"⚙️ Provider: {prov} | Model: {model_name}")

    full_prompt = f"Create 3D Printable CAD Model for Request: {prompt}\n"
    if current_code and current_code.strip():
        full_prompt += (
            f"\nExisting Python Code to Modify:\n```python\n{current_code}\n```\n"
            "Modify the code according to the request while maintaining a valid `mesh` object."
        )

    def call_gemini(contents: Any) -> str:
        nonlocal used_model
        ai_client = get_genai_client(key)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION, temperature=0.2
        )
        try:
            response = ai_client.models.generate_content(
                model=used_model, contents=contents, config=config
            )
        except Exception as err:
            if "404" in str(err) and used_model != DEFAULT_GOOGLE_MODEL:
                emit_log(
                    f"⚠️ Model '{used_model}' is not available; falling back to '{DEFAULT_GOOGLE_MODEL}'."
                )
                used_model = DEFAULT_GOOGLE_MODEL
                response = ai_client.models.generate_content(
                    model=used_model, contents=contents, config=config
                )
            else:
                raise
        return response.text or ""

    def call_llm(text_prompt: str) -> str:
        if prov == "google":
            return call_gemini(text_prompt)
        if prov == "anthropic":
            return query_anthropic_llm(text_prompt, key, model_name)
        return query_openai_compatible_llm(text_prompt, endpoint, key, model_name)

    # Turn 1: initial code generation.
    emit_log("🧠 Generating Python CAD code...")
    try:
        code = extract_python_code(call_llm(full_prompt))
    except CadGenerationError as err:
        raise CadGenerationError(str(err), "\n".join(events)) from err
    except Exception as err:
        emit_log(f"❌ LLM call failed: {err}")
        raise CadGenerationError(f"LLM call failed: {err}", "\n".join(events)) from err
    if not code:
        raise CadGenerationError(
            "The model did not return a Python code block.", "\n".join(events)
        )

    # Execute, with up to MAX_FIX_ATTEMPTS auto-fix rounds.
    exec_log = ""
    mesh = None
    for attempt in range(MAX_FIX_ATTEMPTS + 1):
        try:
            mesh, exec_log = execute_python_3d_code(code)
            emit_log(
                f"📦 Mesh created: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces."
            )
            break
        except RuntimeError as exec_err:
            if attempt == MAX_FIX_ATTEMPTS:
                emit_log("❌ Code still fails after auto-fix attempts.")
                raise CadGenerationError(
                    "Generated code failed to run after auto-fix attempts.",
                    "\n".join(events) + "\n" + str(exec_err),
                ) from exec_err
            emit_log(
                f"⚡ Code failed (attempt {attempt + 1}); asking the model to fix it..."
            )
            try:
                fixed = extract_python_code(
                    call_llm(_build_fix_prompt(prompt, code, str(exec_err)))
                )
            except Exception as err:
                raise CadGenerationError(
                    f"LLM call failed during auto-fix: {err}", "\n".join(events)
                ) from err
            if fixed:
                code = fixed

    # Turn 2: optional visual refinement (Gemini is multimodal).
    if (
        enable_vlm_refinement
        and prov == "google"
        and isinstance(mesh, trimesh.Trimesh)
        and len(mesh.faces) > 0
    ):
        emit_log("📷 Rendering snapshots for visual inspection...")
        try:
            vlm_contents: list[Any] = [
                f"You are evaluating the 3D model generated for: '{prompt}'.\n"
                f"Current Code:\n```python\n{code}\n```\n"
                "Inspect the attached renderings (isometric, top, side). If the model does not match "
                "the request, return complete revised Python code in a ```python block. If it already "
                "matches, reply with the single word OK and no code."
            ]
            vlm_contents += [
                types.Part.from_bytes(data=png, mime_type="image/png")
                for png in render_mesh_snapshots(mesh)
            ]
            refined_code = extract_python_code(call_gemini(vlm_contents))
            if refined_code and refined_code != code:
                emit_log("✨ Applying suggested refinement...")
                try:
                    refined_mesh, refined_log = execute_python_3d_code(refined_code)
                    if len(refined_mesh.faces) > 0:
                        mesh, code, exec_log = refined_mesh, refined_code, refined_log
                        emit_log("🎉 Visual refinement applied.")
                except RuntimeError as ref_err:
                    emit_log(
                        f"⚠️ Refinement code failed ({str(ref_err).splitlines()[-1]}); keeping the first model."
                    )
            else:
                emit_log("✅ Visual check passed; no changes needed.")
        except Exception as vlm_err:
            emit_log(f"⚠️ Visual refinement skipped: {vlm_err}")

    exported = export_mesh_data(mesh)
    emit_log(
        f"🏁 Done. Watertight: {exported['stats']['is_watertight']} | "
        f"Bounding box: {exported['stats']['bounding_box_mm']} mm"
    )

    return {
        "code": code,
        "explanation": f"Generated by {used_model} ({prov})",
        "log": "\n".join(events) + "\n" + exec_log,
        "stats": exported["stats"],
        "obj_data": exported["obj_data"],
        "stl_bytes": exported["stl_bytes"],
    }
