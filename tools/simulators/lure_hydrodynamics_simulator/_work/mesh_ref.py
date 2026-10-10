"""Reference mass properties (trimesh) used to cross-check the JS engine.

Usage: .venv/bin/python mesh_ref.py file1.stl [file2.stl ...]
Prints volume (cm^3), centre of volume (mm), unit-density inertia about the
centre (kg*m^2 per (kg/m^3)), bounds, triangle counts and watertightness.
"""
import sys

import numpy as np
import trimesh

for p in sys.argv[1:]:
  m = trimesh.load(p, force="mesh", process=True)
  print("==", p)
  print("  triangles:", len(m.faces), "vertices:", len(m.vertices),
        "watertight:", m.is_watertight, "winding ok:", m.is_winding_consistent)
  print("  bounds min (mm):", np.round(m.bounds[0], 3), "max:", np.round(m.bounds[1], 3))
  print("  volume (cm^3): %.4f" % (m.volume / 1000.0))
  print("  area (cm^2): %.4f" % (m.area / 100.0))
  print("  centre of volume (mm):", np.round(m.center_mass, 4))
  # trimesh moment_inertia is for density=1 in mesh units (mm^5); convert to m^5
  inertia = m.moment_inertia * 1e-15
  print("  inertia/density about CoV (m^5):")
  for row in inertia:
    print("    ", " ".join("% .4e" % v for v in row))
  parts = m.split(only_watertight=False)
  print("  connected components:", len(parts),
        "signed volumes (cm^3):", [round(float(c.volume) / 1000.0, 4) for c in parts][:8])
