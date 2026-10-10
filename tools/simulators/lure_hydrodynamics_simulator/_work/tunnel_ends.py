"""Find line-through tunnel openings in repo lure STLs (scratch helper).

For each lure, the tunnel axis comes from the SCAD source. Vertices that lie on
the tunnel wall (distance to axis ~ hole radius) are collected; the extreme
projections along the axis give the two openings (entry = front, exit = rear).
"""
import numpy as np
import trimesh


def tunnel_ends(path, p0, p1, radius, tol=0.6):
  m = trimesh.load(path, force="mesh", process=True)
  v = m.vertices
  p0 = np.asarray(p0, float)
  p1 = np.asarray(p1, float)
  axis = (p1 - p0) / np.linalg.norm(p1 - p0)
  rel = v - p0
  s = rel @ axis
  perp = rel - np.outer(s, axis)
  d = np.linalg.norm(perp, axis=1)
  sel = np.abs(d - radius) < tol
  if not sel.any():
    print(path, "no tunnel wall vertices found")
    return
  smin, smax = s[sel].min(), s[sel].max()
  print(path)
  print("  wall verts:", int(sel.sum()), " s range: %.2f .. %.2f" % (smin, smax))
  print("  entry (front) ~", np.round(p0 + axis * smin, 2))
  print("  exit  (rear)  ~", np.round(p0 + axis * smax, 2))


# King salmon cut plug: hull of spheres d=4.2 at (18,0,-9) and (50,0,15).
tunnel_ends("/tmp/scadcheck_king_salmon_cut_plug.stl", (18, 0, -9), (50, 0, 15), 2.1)
# Hoochie wiggler: hull (0,11,0)->(0,28.5,-1.125) in model frame, then
# rotate([0,90,0]) : (x,y,z)->(z,y,-x) and translate z+7.
tunnel_ends("/tmp/scadcheck_fishing_hoochie_wiggler.stl", (-1.125, 28.5, 7), (0, 11, 7), 1.0, tol=0.35)
