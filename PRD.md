# Product Requirement Document (PRD): 3D Printer Agentic Studio

## 1. Executive Summary
The **3D Printer Agentic Studio** is an AI-powered parametric CAD generation platform. It enables users to describe 3D models in natural language, generating executable Python code using off-the-shelf CAD libraries (`trimesh`, `manifold3d`). The platform renders 3D models in-browser in real-time and exports watertight binary `.stl` files ready for 3D printing.

---

## 2. Product Architecture & Key Features

### 2.1 Selectable LLM AI Backend
- **Supported Models:** Gemini 2.5 Flash (Fast/Recommended) and Gemini 2.5 Pro (Complex CAD & High Precision).
- **Authentication:** Native Vertex AI credentials via Application Default Credentials (ADC) on Google Cloud Project `gemle-gke-dev`.
- **Self-Correction Reflection Loop:** If generated Python code fails execution, the backend catches the traceback error, feeds it back to Gemini, auto-corrects the code, and re-executes automatically.

### 2.2 Python CAD Execution Engine (`app/mesh_engine.py`)
- **Off-the-Shelf Libraries:** `trimesh`, `numpy`, `math`, `manifold3d` CSG engine.
- **Boolean Operations:** Supports exact watertight Constructive Solid Geometry (`difference`, `union`, `intersection`) via `engine='manifold'`.
- **Export Formats:** Wavefront `.obj` (for WebGL rendering) and binary `.stl` (for 3D printers).

### 2.3 Interactive WebGL 3D Visualizer (`static/index.html`)
- **Three.js Renderer:** OrbitControls (rotate, pan, zoom), lighting, grid floor, wireframe toggle.
- **3D Print Analyzer:** Displays Bounding Box dimensions (mm), Volume (mm³), Face count, and Watertight Status.
- **Code Viewer:** Shows generated Python CAD code.

### 2.4 Production Infrastructure (`deployment/terraform/single-project/`)
- **Hosting:** GKE Autopilot cluster (`demo-agent`) on GCP project `gemle-gke-dev`.
- **Security:** Workload Identity binding `demo-agent-app@gemle-gke-dev.iam.gserviceaccount.com`.
- **Telemetry:** OpenTelemetry logs routed to Cloud Storage and BigQuery dataset `demo_agent_telemetry`.

---

## 3. Workflow & Verification
1. User enters text prompt (e.g. *"Create a 3D printable gear with 12 teeth"*).
2. Backend queries Vertex AI Gemini LLM.
3. Python `trimesh` code executes and exports `.obj` & `.stl`.
4. Mesh stats are calculated and verified watertight (`is_watertight: True`).
5. User views 3D mesh in browser and downloads `.stl` file for 3D printing.
