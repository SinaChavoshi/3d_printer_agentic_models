# 🧊 3D Printer Agentic Studio

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Trimesh](https://img.shields.io/badge/Trimesh-4.0+-orange.svg)](https://trimesh.org/)
[![Three.js](https://img.shields.io/badge/Three.js-r128-black.svg)](https://threejs.org/)

An AI-powered parametric 3D CAD application that converts text descriptions into executable Python 3D geometry code, renders interactive 3D WebGL models in-browser, and exports watertight binary `.stl` files for 3D printing.

---

## 🌟 Key Features

* **AI-Driven Parametric CAD:** Uses Vertex AI Gemini (Gemini 2.5 Flash / Gemini 2.5 Pro) to generate valid Python `trimesh` code.
* **Auto-Correction Reflection Loop:** Automatically catches Python runtime/geometry errors and sends traceback back to Gemini to self-correct and re-execute code.
* **Watertight CSG Boolean Engine:** Integrated `manifold3d` CSG engine for reliable boolean subtractions (`difference`), unions, and intersections.
* **Interactive 3D Web Visualizer:** Built with Three.js, OrbitControls, grid floor, lighting, and wireframe toggle.
* **3D Print Analyzer:** Displays bounding box dimensions (mm), estimated volume (mm³), triangle face count, and watertight status verification.
* **Instant STL Download:** One-click binary `.stl` file download ready for 3D printing.

---

## 🏗️ Project Architecture

```
3d-printer-agentic-models/
├── app/
│   ├── __init__.py
│   ├── cad_agent.py      # Vertex AI Gemini LLM CAD Agent & Reflection Loop
│   ├── mesh_engine.py    # Python 3D execution engine & manifold3d CSG ops
│   └── server.py         # FastAPI Web Server (/api/generate, /api/export/stl)
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
Apache 2.0 License. See LICENSE for details.
