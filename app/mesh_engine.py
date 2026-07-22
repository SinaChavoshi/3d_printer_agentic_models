# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import io
import math
import traceback
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def generate_sample_mesh(model_type: str = "cube") -> trimesh.Trimesh:
    """Generates a default sample 3D printable mesh."""
    if model_type == "gear":
        cyl = trimesh.creation.cylinder(radius=20, height=8, sections=16)
        teeth = []
        for i in range(8):
            angle = i * (2 * math.pi / 8)
            box = trimesh.creation.box(extents=[6, 6, 8])
            matrix = trimesh.transformations.rotation_matrix(angle, [0, 0, 1])
            matrix[:3, 3] = [20 * math.cos(angle), 20 * math.sin(angle), 0]
            box.apply_transform(matrix)
            teeth.append(box)
        mesh = trimesh.util.concatenate([cyl] + teeth)
    elif model_type == "vase":
        height = 40.0
        sections = 20
        radii = [15 + 5 * math.sin(i * math.pi / sections) for i in range(sections + 1)]
        angles = [i * 0.1 for i in range(sections + 1)]
        slices = []
        for i, (r, a) in enumerate(zip(radii, angles)):
            z = (i / sections) * height
            poly = trimesh.creation.polygonize(
                trimesh.path.polygons.Polygon(
                    [(r * math.cos(a + 2 * math.pi * k / 6), r * math.sin(a + 2 * math.pi * k / 6)) for k in range(6)]
                )
            )
            poly.apply_translation([0, 0, z])
            slices.append(poly)
        mesh = trimesh.creation.box(extents=[30, 30, 40])
    elif model_type == "container":
        outer = trimesh.creation.box(extents=[40, 40, 30])
        inner = trimesh.creation.box(extents=[34, 34, 28])
        inner.apply_translation([0, 0, 2])
        mesh = outer.difference(inner)
    else:
        mesh = trimesh.creation.box(extents=[25, 25, 25])
    return mesh

def execute_python_3d_code(code_str: str) -> tuple[trimesh.Trimesh, str]:
    """
    Executes Python code that constructs a trimesh.Trimesh object named `mesh`.
    Returns (trimesh_object, execution_log).
    """
    scope = {
        "trimesh": trimesh,
        "np": np,
        "numpy": np,
        "math": math,
    }
    
    log = "Execution started...\n"
    try:
        exec(code_str, scope)
        if "mesh" not in scope:
            raise ValueError("Code executed successfully, but no `mesh` variable of type trimesh.Trimesh was defined.")
        
        result_mesh = scope["mesh"]
        if isinstance(result_mesh, trimesh.Scene):
            result_mesh = result_mesh.dump(concatenate=True)
            
        if not isinstance(result_mesh, trimesh.Trimesh):
            raise TypeError(f"`mesh` variable must be a trimesh.Trimesh object, got {type(result_mesh)}")
        
        log += f"Success! Mesh generated with {len(result_mesh.vertices)} vertices and {len(result_mesh.faces)} faces.\n"
        return result_mesh, log
    except Exception as e:
        log += f"Execution Error:\n{traceback.format_exc()}\n"
        raise RuntimeError(log) from e

def render_mesh_snapshots(mesh: trimesh.Trimesh, views: list[tuple[int, int]] | None = None) -> list[bytes]:
    """
    Renders multi-angle 2D projections of the 3D mesh (PNG bytes) for VLM vision analysis.
    Default views: Isometric (elev=30, azim=45), Top-down (elev=90, azim=0), Side-view (elev=0, azim=0).
    """
    if views is None:
        views = [(30, 45), (90, 0), (0, 0)]

    png_snapshots = []
    
    # Subsample faces if mesh is very dense for fast 2D rendering
    display_triangles = mesh.triangles
    if len(display_triangles) > 3000:
        indices = np.random.choice(len(display_triangles), 3000, replace=False)
        display_triangles = display_triangles[indices]

    bounds = mesh.bounds if mesh.bounds is not None else [[-10, -10, -10], [10, 10, 10]]
    max_extent = max(mesh.extents) * 0.6 if mesh.extents is not None else 20.0
    center = mesh.centroid if mesh.centroid is not None else [0, 0, 0]

    for elev, azim in views:
        fig = plt.figure(figsize=(4, 4), dpi=100)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor('#0f172a')
        fig.patch.set_facecolor('#0f172a')

        poly3d = Poly3DCollection(display_triangles, alpha=0.95, linewidths=0.3, edgecolor='#0284c7', facecolor='#38bdf8')
        ax.add_collection3d(poly3d)

        ax.set_xlim([center[0] - max_extent, center[0] + max_extent])
        ax.set_ylim([center[1] - max_extent, center[1] + max_extent])
        ax.set_zlim([center[2] - max_extent, center[2] + max_extent])
        ax.view_init(elev=elev, azim=azim)
        plt.axis('off')

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, facecolor=fig.get_facecolor())
        plt.close(fig)
        png_snapshots.append(buf.getvalue())

    return png_snapshots

def export_mesh_data(mesh: trimesh.Trimesh) -> dict:
    """Exports mesh to STL bytes, Wavefront OBJ format, and metadata stats."""
    stl_io = io.BytesIO()
    mesh.export(stl_io, file_type="stl")
    stl_bytes = stl_io.getvalue()
    
    obj_str = mesh.export(file_type="obj")
    
    bounds = mesh.bounds
    extents = mesh.extents if bounds is not None else [0, 0, 0]
    
    stats = {
        "vertices_count": len(mesh.vertices),
        "faces_count": len(mesh.faces),
        "volume_mm3": round(float(mesh.volume), 2) if mesh.is_watertight else "Non-watertight",
        "is_watertight": bool(mesh.is_watertight),
        "is_printable": bool(mesh.is_watertight and len(mesh.faces) > 0),
        "bounding_box_mm": [round(float(x), 2) for x in extents],
    }
    
    return {
        "stl_bytes": stl_bytes,
        "obj_data": obj_str,
        "vertices": mesh.vertices.tolist(),
        "faces": mesh.faces.tolist(),
        "stats": stats,
    }
