# Product Requirement Document (PRD): 3D Printer Agentic Studio

## 1. Executive Summary
The **3D Printer Agentic Studio** is an AI-powered parametric CAD generation tool. Users describe a part in natural language; an LLM generates Python code using off-the-shelf CAD libraries (`trimesh`, `manifold3d`); the code runs in a sandbox; and the result is shown in the browser and exported as a watertight binary `.stl` for 3D printing.

---

## 2. Product Architecture & Key Features

### 2.1 Selectable LLM Backend (`app/cad_agent.py`)
- **Providers:** Google Gemini (API key or Vertex AI via Application Default Credentials), Anthropic, OpenAI, xAI, DeepSeek, Kimi/Moonshot, and self-hosted OpenAI-compatible servers.
- **Key isolation:** each provider only receives its own key; custom endpoints must be allowlisted by the operator.
- **Self-correction loop:** if generated code fails, the user request, the failing code, and the error are sent back to the model (up to 2 retries). Persistent failures are reported to the user.
- **Visual refinement (Gemini):** rendered snapshots of the result are reviewed by the model, which may revise the code.

### 2.2 Sandboxed CAD Execution Engine (`app/mesh_engine.py`)
- Generated code runs in a separate Python process with a timeout and memory limit, and may only use `trimesh`, `numpy`, and `math`.
- **Boolean operations:** watertight CSG (`difference`, `union`, `intersection`) via `engine='manifold'`.
- **Export formats:** Wavefront `.obj` (for WebGL rendering) and binary `.stl` (for 3D printers).

### 2.3 Interactive WebGL Visualizer (`static/index.html`)
- **Three.js renderer:** OrbitControls, lighting, grid floor, wireframe toggle.
- **3D print analyzer:** bounding box (mm), volume (mm³), face count, watertight status.
- **Code viewer:** shows the generated Python CAD code; follow-up prompts modify the current model.

### 2.4 Deployment
- Container image (`Dockerfile`) running as a non-root user on port 8080.
- Any network-reachable deployment must set `STUDIO_ACCESS_TOKEN`.

---

## 3. Workflow & Verification
1. User enters a text prompt (e.g. *"Create a 3D printable gear with 12 teeth"*).
2. The backend queries the selected LLM.
3. The generated `trimesh` code runs in the sandbox and exports `.obj` & `.stl`.
4. Mesh stats are calculated, including watertightness (`is_watertight: True`).
5. User views the mesh in the browser and downloads the `.stl` for 3D printing.
