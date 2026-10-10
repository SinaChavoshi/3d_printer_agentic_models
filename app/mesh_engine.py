# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""Mesh helpers: sandboxed execution of generated CAD code, snapshots, export."""

import io
import math
import os
import subprocess
import sys
import tempfile

import matplotlib
import numpy as np
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Limits for running untrusted, LLM-generated code.
EXEC_TIMEOUT_SECONDS = int(os.getenv("CAD_EXEC_TIMEOUT_SECONDS", "60"))
EXEC_MEMORY_LIMIT_BYTES = int(os.getenv("CAD_EXEC_MEMORY_MB", "4096")) * 1024 * 1024

# Runs inside a separate, resource-limited Python process. Generated code only
# gets a small allowlist of modules and builtins (no file, network, or process
# access), and the result is passed back as plain arrays.
_SANDBOX_RUNNER = r"""
import builtins, json, math, sys
import numpy as np
import trimesh

ALLOWED_MODULES = {"math", "numpy", "trimesh"}
_real_import = builtins.__import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level != 0 or name.split(".")[0] not in ALLOWED_MODULES:
        raise ImportError(f"Import of '{name}' is not allowed in CAD code.")
    return _real_import(name, globals, locals, fromlist, level)

SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
        "float", "int", "isinstance", "len", "list", "map", "max", "min",
        "pow", "range", "reversed", "round", "set", "slice", "sorted", "str",
        "sum", "tuple", "zip", "print", "Exception", "ValueError",
        "TypeError", "ZeroDivisionError", "IndexError", "KeyError",
    )
}
SAFE_BUILTINS["__import__"] = _safe_import

def main():
    code = sys.stdin.read()
    scope = {"__builtins__": SAFE_BUILTINS, "trimesh": trimesh, "np": np,
             "numpy": np, "math": math}
    exec(compile(code, "<cad_code>", "exec"), scope)
    if "mesh" not in scope:
        raise ValueError("Code ran, but no `mesh` variable of type trimesh.Trimesh was defined.")
    mesh = scope["mesh"]
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"`mesh` must be a trimesh.Trimesh object, got {type(mesh).__name__}")
    np.savez(sys.argv[1], vertices=np.asarray(mesh.vertices, dtype=np.float64),
             faces=np.asarray(mesh.faces, dtype=np.int64))

main()
"""


def _limit_child_resources() -> None:
    """Applied in the child process before exec (POSIX only)."""
    import resource

    resource.setrlimit(
        resource.RLIMIT_AS, (EXEC_MEMORY_LIMIT_BYTES, EXEC_MEMORY_LIMIT_BYTES)
    )
    # CPU seconds across all threads; the wall-clock timeout is enforced separately.
    cpu_limit = EXEC_TIMEOUT_SECONDS * 4
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))


def generate_sample_mesh(model_type: str = "cube") -> trimesh.Trimesh:
    """Generates a default sample 3D printable mesh."""
    if model_type == "gear":
        hub = trimesh.creation.cylinder(radius=20, height=8, sections=48)
        teeth = []
        for i in range(8):
            angle = i * (2 * math.pi / 8)
            tooth = trimesh.creation.box(extents=[6, 6, 8])
            matrix = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
            matrix[:3, 3] = [20 * math.cos(angle), 20 * math.sin(angle), 0]
            tooth.apply_transform(matrix)
            teeth.append(tooth)
        return trimesh.boolean.union([hub, *teeth], engine="manifold")
    if model_type == "container":
        outer = trimesh.creation.box(extents=[40, 40, 30])
        inner = trimesh.creation.box(extents=[34, 34, 28])
        inner.apply_translation([0, 0, 2])
        return outer.difference(inner, engine="manifold")
    return trimesh.creation.box(extents=[25, 25, 25])


def execute_python_3d_code(code_str: str) -> tuple[trimesh.Trimesh, str]:
    """Runs generated CAD code in a sandboxed subprocess.

    The code must assign a trimesh.Trimesh to a variable named `mesh`.
    Returns (mesh, execution_log). Raises RuntimeError with the log on failure.
    """
    log = "Execution started (sandboxed subprocess)...\n"
    with tempfile.TemporaryDirectory(prefix="cad_exec_") as workdir:
        out_path = os.path.join(workdir, "mesh.npz")
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", _SANDBOX_RUNNER, out_path],
                input=code_str,
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT_SECONDS,
                cwd=workdir,
                env={"PATH": os.environ.get("PATH", ""), "OMP_NUM_THREADS": "1"},
                preexec_fn=_limit_child_resources if os.name == "posix" else None,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            log += f"Execution Error:\nTimed out after {EXEC_TIMEOUT_SECONDS}s.\n"
            raise RuntimeError(log) from e

        if proc.returncode != 0 or not os.path.exists(out_path):
            stderr = (
                proc.stderr.strip() or f"Process exited with code {proc.returncode}."
            )
            log += f"Execution Error:\n{stderr}\n"
            raise RuntimeError(log)

        with np.load(out_path) as data:
            mesh = trimesh.Trimesh(
                vertices=data["vertices"], faces=data["faces"], process=True
            )

    log += (
        f"Success! Mesh generated with {len(mesh.vertices)} vertices "
        f"and {len(mesh.faces)} faces.\n"
    )
    return mesh, log


def render_mesh_snapshots(
    mesh: trimesh.Trimesh, views: list[tuple[int, int]] | None = None
) -> list[bytes]:
    """Renders multi-angle PNG snapshots of the mesh for VLM inspection.

    Default views: isometric (30, 45), top-down (90, 0), side (0, 0).
    """
    if views is None:
        views = [(30, 45), (90, 0), (0, 0)]

    display_triangles = mesh.triangles
    if len(display_triangles) > 3000:
        rng = np.random.default_rng(0)  # deterministic subsample
        indices = rng.choice(len(display_triangles), 3000, replace=False)
        display_triangles = display_triangles[indices]

    max_extent = max(mesh.extents) * 0.6 if mesh.extents is not None else 20.0
    center = mesh.centroid if mesh.centroid is not None else [0, 0, 0]

    png_snapshots = []
    for elev, azim in views:
        fig = plt.figure(figsize=(4, 4), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#0f172a")
        fig.patch.set_facecolor("#0f172a")
        ax.add_collection3d(
            Poly3DCollection(
                display_triangles,
                alpha=0.95,
                linewidths=0.3,
                edgecolor="#0284c7",
                facecolor="#38bdf8",
            )
        )
        ax.set_xlim([center[0] - max_extent, center[0] + max_extent])
        ax.set_ylim([center[1] - max_extent, center[1] + max_extent])
        ax.set_zlim([center[2] - max_extent, center[2] + max_extent])
        ax.view_init(elev=elev, azim=azim)
        plt.axis("off")

        buf = io.BytesIO()
        plt.savefig(
            buf,
            format="png",
            bbox_inches="tight",
            pad_inches=0.05,
            facecolor=fig.get_facecolor(),
        )
        plt.close(fig)
        png_snapshots.append(buf.getvalue())

    return png_snapshots


def export_mesh_data(mesh: trimesh.Trimesh) -> dict:
    """Exports mesh to STL bytes, Wavefront OBJ text, and print stats."""
    stl_io = io.BytesIO()
    mesh.export(stl_io, file_type="stl")

    stats = {
        "vertices_count": len(mesh.vertices),
        "faces_count": len(mesh.faces),
        "volume_mm3": round(float(mesh.volume), 2)
        if mesh.is_watertight
        else "Non-watertight",
        "is_watertight": bool(mesh.is_watertight),
        "is_printable": bool(mesh.is_watertight and len(mesh.faces) > 0),
        "bounding_box_mm": [round(float(x), 2) for x in mesh.extents],
    }

    return {
        "stl_bytes": stl_io.getvalue(),
        "obj_data": mesh.export(file_type="obj"),
        "stats": stats,
    }


__all__ = [
    "execute_python_3d_code",
    "export_mesh_data",
    "generate_sample_mesh",
    "render_mesh_snapshots",
]
