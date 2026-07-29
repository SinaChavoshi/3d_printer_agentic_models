# 🧊 3D Printer Agentic Studio

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Trimesh](https://img.shields.io/badge/Trimesh-4.0+-orange.svg)](https://trimesh.org/)
[![Three.js](https://img.shields.io/badge/Three.js-r128-black.svg)](https://threejs.org/)

An AI-powered parametric 3D CAD application that converts text descriptions into executable 3D geometry code (Python and OpenSCAD). It supports rendering interactive 3D WebGL models in-browser, exporting watertight binary `.stl` files for 3D printing, and hosts specialized simulators such as a Lure Hydrodynamics Simulator.

The repository accommodates various generated models based on OpenSCAD, Python, and other generation scripts.

---

## 🌟 Key Features

* **AI-Driven Parametric CAD:** Uses Vertex AI Gemini to generate valid Python `trimesh` and OpenSCAD code.
* **Auto-Correction Reflection Loop:** Automatically catches Python runtime/geometry errors and sends traceback back to Gemini to self-correct and re-execute code.
* **Multi-Language Generation:** Stores and executes models generated via Python and OpenSCAD scripts.
* **Model Simulators:** Includes a Lure Hydrodynamics Simulator to observe how a generated lure model behaves under water current.
* **Watertight CSG Boolean Engine:** Integrated `manifold3d` CSG engine for reliable boolean subtractions (`difference`), unions, and intersections.
* **Interactive 3D Web Visualizer:** Built with Three.js, OrbitControls, grid floor, lighting, and wireframe toggle.
* **3D Print Analyzer:** Displays bounding box dimensions (mm), estimated volume (mm³), triangle face count, and watertight status verification.
* **Instant STL Download:** One-click binary `.stl` file download ready for 3D printing.

---

## 🏗️ Project Architecture

```
3d-printer-agentic-models/
├── app/                  # Main 3D generator AI app
│   ├── __init__.py
│   ├── cad_agent.py      # Vertex AI Gemini LLM CAD Agent & Reflection Loop
│   ├── mesh_engine.py    # Python 3D execution engine & manifold3d CSG ops
│   └── server.py         # FastAPI Web Server (/api/generate, /api/export/stl)
├── simulators/           # Simulation tools
│   └── lure_hydrodynamics_simulator/  # Lure hydrodynamics testing
├── generated_models/     # Generator scripts (binary STLs are gitignored)
│   ├── python/           # Python (.py) scripts for models
│   └── openscad/         # OpenSCAD (.scad) scripts for models
├── static/
│   └── index.html        # Three.js 3D Visualizer & Studio Web UI
├── tests/
│   └── test_mesh_engine.py  # Unit & Integration Test Suite
├── PRD.md                # Formal Product Requirement Document
├── Dockerfile            # Production Container Image
└── pyproject.toml        # Dependencies
```

---

## 🚀 Getting Started

### Prerequisites
* Python 3.11 or higher
* [`uv`](https://docs.astral.sh/uv/) package manager (recommended) or `pip`
* Google Cloud ADC credentials (for Vertex AI Gemini access)

### 1. Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/SinaChavoshi/3d_printer_agentic_models.git
cd 3d_printer_agentic_models
uv sync
```

### 2. Running the Server Locally
Start the FastAPI application:

```bash
uv run uvicorn app.server:app --host 0.0.0.0 --port 8088
```

Open your browser to **`http://localhost:8088`** to access the 3D Agent Studio.

---

## 🧪 Running Tests

Run the test suite using `pytest`:

```bash
uv run pytest tests/test_mesh_engine.py
```

---

## 📖 Sample Prompts to Try

1. **Mechanical Gear:**
   `Create a 3D printable mechanical gear with 12 teeth and a square mounting hole.`
2. **Hollow Pen Holder:**
   `Generate a 3D printable hexagonal pen holder container 100mm tall with 4mm thick walls.`
3. **Twisted Vase:**
   `Generate a 3D printable twisted spiral vase with a flared top rim.`

---

## 📄 License

This application is free to use for personal applications, but not for commercial use. You may share and modify it with attribution.

These terms align with standard 3D printing community licenses (e.g., Printables):
*   ✖ **Sharing without ATTRIBUTION** (Attribution is required)
*   ✔ **Remix Culture allowed** (You can modify and edit the code/models)
*   ✖ **Commercial Use** (Free for personal applications only)
*   ✔ **Free Cultural Works**
*   ✔ **Meets Open Definition**
