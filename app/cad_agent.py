# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import os
import re
import traceback
from typing import Callable, Any
import trimesh
import httpx
import google.auth
from google.genai import client, types
from app.mesh_engine import (
    execute_python_3d_code,
    generate_sample_mesh,
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
3. Available pre-imported modules: `trimesh`, `np` (numpy), `math`.
4. Standard 3D geometry builders:
   - Boxes: `trimesh.creation.box(extents=[w, l, h])`
   - Cylinders: `trimesh.creation.cylinder(radius=r, height=h, sections=32)`
   - Spheres: `trimesh.creation.icosphere(subdivisions=3, radius=r)`
   - Cones: `trimesh.creation.cone(radius=r, height=h, sections=32)`
   - Hollow Tubes/Annulus: `trimesh.creation.annulus(r_min=r1, r_max=r2, height=h, sections=32)`
5. Boolean CSG Operations & Transformations:
   - `mesh1.difference(mesh2, engine='manifold')` (Subtractions/Holes)
   - `mesh1.union(mesh2, engine='manifold')` (Unions)
   - `trimesh.util.concatenate([mesh1, mesh2, mesh3])`
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

def extract_python_code(llm_response_text: str) -> str:
    """Extracts Python code block from LLM response."""
    match = re.search(r"```python\s*(.*?)\s*```", llm_response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", llm_response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response_text.strip()

def get_genai_client(api_key: str | None = None):
    """Initializes Google GenAI Client with Vertex AI ADC or API Key."""
    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip():
        return client.Client(api_key=key.strip())
    
    try:
        _, project_id = google.auth.default()
    except Exception:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "gemle-gke-dev")
        
    project_id = project_id or "gemle-gke-dev"
    region = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    return client.Client(vertexai=True, project=project_id, location=region)

def query_anthropic_llm(
    prompt: str,
    api_key: str | None = None,
    model_name: str = "claude-3-7-sonnet-20250219",
) -> str:
    """Queries Anthropic API (Claude 3.7 Sonnet, Claude 3.5 Sonnet, Haiku)."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key or not key.strip():
        raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY env var or enter API key in UI settings.")
    
    headers = {
        "x-api-key": key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model_name,
        "max_tokens": 4096,
        "system": SYSTEM_INSTRUCTION,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=60.0) as http_client:
        resp = http_client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

def query_openai_compatible_llm(
    prompt: str,
    base_url: str,
    api_key: str | None = None,
    model_name: str = "gpt-4o",
) -> str:
    """Queries OpenAI, DeepSeek, Kimi/Moonshot, or Self-Hosted OpenAI-compatible APIs."""
    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"
        
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    
    with httpx.Client(timeout=60.0) as http_client:
        resp = http_client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

def generate_cad_model(
    prompt: str,
    current_code: str | None = None,
    model_name: str = "gemini-2.5-pro",
    api_key: str | None = None,
    base_url: str | None = None,
    provider: str = "google",
    enable_vlm_refinement: bool = True,
    log_callback: Callable[[str], Any] | None = None,
) -> dict:
    """
    Multi-Provider 3D CAD Generation with Multi-Turn VLM Visual Feedback Loop.
    Supports: Google Gemini (Vertex AI / Key), Anthropic Claude, OpenAI, DeepSeek, Kimi (Moonshot), & Self-Hosted LLMs.
    """
    def emit_log(msg: str):
        if log_callback:
            log_callback(msg)

    prov = provider.lower().strip()
    emit_log(f"🚀 Initializing CAD Generation for prompt: '{prompt}'")
    emit_log(f"⚙️ Model: {model_name} | Provider: {prov}")

    full_prompt = f"Create 3D Printable CAD Model for Request: {prompt}\n"
    if current_code and current_code.strip():
        full_prompt += f"\nExisting Python Code to Modify:\n```python\n{current_code}\n```\nModify the code according to the request while maintaining a valid `mesh` object."

    def call_llm(text_prompt: str) -> str:
        if prov == "anthropic":
            return query_anthropic_llm(text_prompt, api_key=api_key, model_name=model_name)
        elif prov == "openai":
            key = api_key or os.getenv("OPENAI_API_KEY")
            return query_openai_compatible_llm(text_prompt, "https://api.openai.com/v1", api_key=key, model_name=model_name)
        elif prov == "deepseek":
            key = api_key or os.getenv("DEEPSEEK_API_KEY")
            url = base_url or "https://api.deepseek.com/v1"
            return query_openai_compatible_llm(text_prompt, url, api_key=key, model_name=model_name)
        elif prov in ["kimi", "moonshot"]:
            key = api_key or os.getenv("MOONSHOT_API_KEY")
            url = base_url or "https://api.moonshot.cn/v1"
            return query_openai_compatible_llm(text_prompt, url, api_key=key, model_name=model_name)
        elif prov in ["self-hosted", "local"]:
            url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
            return query_openai_compatible_llm(text_prompt, url, api_key=api_key, model_name=model_name)
        else: # Google Gemini (Vertex AI / Key)
            ai_client = get_genai_client(api_key=api_key)
            response = ai_client.models.generate_content(
                model=model_name,
                contents=text_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2,
                ),
            )
            return response.text or ""

    # Turn 1: Initial Code Generation
    emit_log("🧠 [Turn 1/2] Generating initial Python CAD code with LLM...")
    
    try:
        raw_text = call_llm(full_prompt)
        code = extract_python_code(raw_text)
        emit_log("✅ Code generated. Executing 3D geometry engine...")
    except Exception as llm_err:
        emit_log(f"⚠️ LLM Call Error: {str(llm_err)}. Falling back to base mesh.")
        code = "# Fallback Box\nmesh = trimesh.creation.box(extents=[25, 25, 25])"

    # Turn 1 Execution
    try:
        mesh, log_str = execute_python_3d_code(code)
        emit_log(f"📦 Mesh created! {len(mesh.vertices)} vertices, {len(mesh.faces)} faces.")
    except Exception as exec_err:
        emit_log(f"⚡ Code execution error: {str(exec_err)}. Triggering auto-fix...")
        fix_prompt = (
            f"Execution Error in code:\n```\n{str(exec_err)}\n```\n"
            f"Please fix the code and return valid python code assigning result to `mesh`."
        )
        try:
            fix_text = call_llm(fix_prompt)
            code = extract_python_code(fix_text)
            mesh, log_str = execute_python_3d_code(code)
            emit_log("✅ Auto-corrected code executed successfully.")
        except Exception:
            mesh = generate_sample_mesh("cube")
            code = "# Fallback Box\nmesh = trimesh.creation.box(extents=[25, 25, 25])"

    # Turn 2: VLM Visual Evaluation & Refinement Loop (Available for Gemini & Multimodal models)
    if enable_vlm_refinement and prov == "google" and isinstance(mesh, trimesh.Trimesh) and len(mesh.faces) > 0:
        emit_log("📷 [Turn 2/2] Rendering multi-angle 2D snapshots for VLM Vision Inspection...")
        try:
            png_snapshots = render_mesh_snapshots(mesh)
            emit_log(f"👁️ Created {len(png_snapshots)} view snapshots (Isometric, Top, Side).")
            emit_log("🧠 VLM evaluating visual quality & alignment against prompt...")

            ai_client = get_genai_client(api_key=api_key)
            vlm_contents = [
                f"You are evaluating the visual quality of the 3D model generated for: '{prompt}'.\n"
                f"Current Code:\n```python\n{code}\n```\n"
                f"Inspect the attached 2D snapshot renderings of the 3D model. "
                f"Does the model match the user's intent? Are there any missing elements or visual flaws? "
                f"If improvements are needed, output revised Python code producing an upgraded `mesh` object. Otherwise, return the code as is."
            ]

            for png_bytes in png_snapshots:
                vlm_contents.append(types.Part.from_bytes(data=png_bytes, mime_type="image/png"))

            vlm_resp = ai_client.models.generate_content(
                model=model_name,
                contents=vlm_contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.2,
                ),
            )

            vlm_text = vlm_resp.text or ""
            refined_code = extract_python_code(vlm_text)
            
            if refined_code and len(refined_code) > 20:
                emit_log("✨ VLM suggested code refinement. Re-executing geometry...")
                try:
                    refined_mesh, _ = execute_python_3d_code(refined_code)
                    if isinstance(refined_mesh, trimesh.Trimesh) and len(refined_mesh.faces) > 0:
                        mesh = refined_mesh
                        code = refined_code
                        emit_log("🎉 VLM visual refinement successfully applied!")
                except Exception as ref_err:
                    emit_log(f"⚠️ VLM refinement code error: {str(ref_err)}. Retaining initial mesh.")

        except Exception as vlm_err:
            emit_log(f"⚠️ VLM Snapshot evaluation skipped: {str(vlm_err)}")

    emit_log("🏁 Finalizing STL export & WebGL payload...")
    exported = export_mesh_data(mesh)
    emit_log(f"🎉 Complete! Watertight: {exported['stats']['is_watertight']} | Bounding Box: {exported['stats']['bounding_box_mm']}")

    return {
        "code": code,
        "explanation": f"Generated by {model_name} ({prov})",
        "log": log_str,
        "stats": exported["stats"],
        "obj_data": exported["obj_data"],
        "stl_bytes": exported["stl_bytes"],
    }
