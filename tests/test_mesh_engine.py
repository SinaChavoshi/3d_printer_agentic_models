# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import pytest
import trimesh
from app.mesh_engine import generate_sample_mesh, execute_python_3d_code, export_mesh_data
from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def test_generate_sample_mesh():
    mesh = generate_sample_mesh("cube")
    assert isinstance(mesh, trimesh.Trimesh)
    assert mesh.is_watertight
    assert len(mesh.vertices) > 0

def test_execute_python_3d_code_valid():
    code = """
import trimesh
box = trimesh.creation.box(extents=[20, 20, 20])
hole = trimesh.creation.cylinder(radius=5, height=30)
mesh = box.difference(hole, engine='manifold')
"""
    mesh, log = execute_python_3d_code(code)
    assert isinstance(mesh, trimesh.Trimesh)
    assert mesh.is_watertight
    assert "Success" in log

def test_export_mesh_data():
    mesh = generate_sample_mesh("gear")
    data = export_mesh_data(mesh)
    assert "stl_bytes" in data
    assert "obj_data" in data
    assert data["stats"]["is_watertight"] is True
    assert len(data["stl_bytes"]) > 0

def test_fastapi_endpoints():
    # Test models endpoint
    res = client.get("/api/models")
    assert res.status_code == 200
    assert "models" in res.json()

    # Test generate endpoint (using local fallback/sample)
    gen_res = client.post("/api/generate", json={"prompt": "Create a 3D printable cube", "model_name": "gemini-2.5-flash"})
    assert gen_res.status_code == 200
    body = gen_res.json()
    assert "session_id" in body
    assert "obj_data" in body
    assert "code" in body

    # Test STL export endpoint
    session_id = body["session_id"]
    stl_res = client.get(f"/api/export/{session_id}/stl")
    assert stl_res.status_code == 200
    assert stl_res.headers["content-type"] == "application/sla"
