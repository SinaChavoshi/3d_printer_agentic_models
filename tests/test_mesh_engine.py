# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import pytest
import trimesh

from app import mesh_engine
from app.mesh_engine import (
    execute_python_3d_code,
    export_mesh_data,
    generate_sample_mesh,
)


@pytest.mark.parametrize("model_type", ["cube", "gear", "container"])
def test_generate_sample_mesh_is_watertight(model_type):
    mesh = generate_sample_mesh(model_type)
    assert isinstance(mesh, trimesh.Trimesh)
    assert mesh.is_watertight
    assert len(mesh.faces) > 0


def test_execute_python_3d_code_valid():
    code = (
        "box = trimesh.creation.box(extents=[20, 20, 20])\n"
        "hole = trimesh.creation.cylinder(radius=5, height=30)\n"
        "mesh = box.difference(hole, engine='manifold')\n"
    )
    mesh, log = execute_python_3d_code(code)
    assert isinstance(mesh, trimesh.Trimesh)
    assert mesh.is_watertight
    assert "Success" in log


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("import os\nmesh = trimesh.creation.box()", "not allowed"),
        ("import subprocess\nmesh = trimesh.creation.box()", "not allowed"),
        ("open('/tmp/should_not_exist', 'w')\nmesh = trimesh.creation.box()", "open"),
        ("__import__('os')\nmesh = trimesh.creation.box()", "not allowed"),
        ("x = 1", "no `mesh` variable"),
        ("mesh = 5", "must be a trimesh.Trimesh"),
    ],
)
def test_execute_python_3d_code_rejects_unsafe_or_invalid_code(code, expected):
    with pytest.raises(RuntimeError, match=expected):
        execute_python_3d_code(code)


def test_execute_python_3d_code_times_out(monkeypatch):
    monkeypatch.setattr(mesh_engine, "EXEC_TIMEOUT_SECONDS", 2)
    with pytest.raises(RuntimeError, match="Timed out"):
        execute_python_3d_code("while True:\n    pass")


def test_export_mesh_data():
    data = export_mesh_data(generate_sample_mesh("gear"))
    assert data["stl_bytes"]
    assert data["obj_data"]
    assert data["stats"]["is_watertight"] is True
    assert data["stats"]["is_printable"] is True
