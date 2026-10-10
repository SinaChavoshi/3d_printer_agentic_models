#!/usr/bin/env python3
"""
prepare_case.py - build an OpenFOAM (ESI/OpenCFD v2412) overset 6-DoF case for
a 3D-printed trolling lure towed on a leader.

Pipeline (nothing here runs OpenFOAM):

  1. load the lure STL (OpenSCAD exports millimetres), scale to metres;
  2. orient it: long axis along +x (flow direction), nose upstream (min x),
     "up" along +z;
  3. estimate the *printed* mass properties (perimeter shell + sparse infill,
     optional point ballast): mass, centre of mass, inertia tensor about the
     CoM -> principal moments + principal axes (OpenFOAM's sixDoF solver wants
     a diagonal inertia plus an orientation tensor);
  4. hydrostatics: displaced volume, centre of buoyancy, net weight;
  5. tow point (auto = front-most surface point on the body centre line) and
     leader geometry (anchor placed at the estimated equilibrium line angle);
  6. copy ./template to the output directory and replace every @@TOKEN@@
     (6-DoF block, restraints, inlet velocity / ramp / bounded fluctuations,
     domain size, refinement boxes, snappyHexMesh levels, time step ...);
  7. write the oriented STL to lureMesh/constant/triSurface/lure.stl,
     case_info.json (read by postprocess.py) and README_CASE.md;
  8. self-check: no leftover tokens, balanced braces/parentheses.

Example:
    python prepare_case.py /tmp/scadcheck_king_salmon_cut_plug.stl \
        --speed-mph 2.5 --mesh-level medium -o cases/cut_plug_2p5mph

Requires: numpy, trimesh (scipy optional: enables the voxel shell model).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

try:
    import trimesh
except ImportError:  # pragma: no cover - environment issue
    sys.exit("prepare_case.py needs the 'trimesh' package (pip install trimesh)")

try:  # optional - voxel shell/infill model uses a Euclidean distance transform
    from scipy import ndimage as _ndimage
except Exception:  # pragma: no cover - optional dependency
    _ndimage = None


HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE / "template"
OPENFOAM_RELEASE = "OpenFOAM v2412 (ESI/OpenCFD, www.openfoam.com)"

MPH_TO_MS = 0.44704
G0 = 9.80665
UNIT_SCALE = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254}

# Water properties (ITTC 2011 fresh water / sea water at 35 g/kg):
# (temperature C, density kg/m3, kinematic viscosity m2/s)
WATER_TABLE = {
    "fresh": [
        (0.0, 999.84, 1.7918e-6),
        (5.0, 999.97, 1.5182e-6),
        (10.0, 999.70, 1.3059e-6),
        (15.0, 999.10, 1.1386e-6),
        (20.0, 998.21, 1.0034e-6),
        (25.0, 997.05, 0.8926e-6),
        (30.0, 995.65, 0.8007e-6),
    ],
    "salt": [
        (0.0, 1028.11, 1.8284e-6),
        (5.0, 1027.68, 1.5545e-6),
        (10.0, 1026.95, 1.3517e-6),
        (15.0, 1025.97, 1.1892e-6),
        (20.0, 1024.76, 1.0508e-6),
        (25.0, 1023.34, 0.9468e-6),
        (30.0, 1021.73, 0.8604e-6),
    ],
}

# Mesh presets. bg_cells_per_L = cells per lure length in the finest background
# box (= base cell of the component mesh). Surface levels are snappyHexMesh
# levels relative to that base cell (cell size halves per level).
MESH_PRESETS = {
    "coarse": dict(bg_cells_per_L=16, surf=(2, 3), wake=1, layers=0),
    "medium": dict(bg_cells_per_L=24, surf=(3, 4), wake=2, layers=3),
    "fine": dict(bg_cells_per_L=32, surf=(4, 5), wake=3, layers=5),
}
N_BG_LEVELS = 3  # nested refinement boxes in the background snappyHexMeshDict

TOKEN_RE = re.compile(r"@@[A-Z0-9_]+@@")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def fnum(x: float, sig: int = 9) -> str:
    """Compact float formatting for OpenFOAM dictionaries (float noise
    below 1e-14 is written as 0)."""
    x = float(x)
    if abs(x) < 1e-14 or not math.isfinite(x):
        return "0"
    s = f"{x:.{sig}g}"
    if "e" in s:
        mant, exp = s.split("e")
        s = f"{mant}e{int(exp)}"
    return s


def fvec(v, sig: int = 9) -> str:
    return " ".join(fnum(c, sig) for c in np.asarray(v, dtype=float).ravel())


def parse_xyz(text: str, what: str) -> np.ndarray:
    try:
        vals = [float(t) for t in re.split(r"[,\s]+", text.strip()) if t]
    except ValueError as exc:
        raise SystemExit(f"{what}: expected 'x,y,z', got '{text}'") from exc
    if len(vals) != 3:
        raise SystemExit(f"{what}: expected 3 numbers 'x,y,z', got '{text}'")
    return np.array(vals, dtype=float)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def water_properties(kind: str, temp_c: float):
    table = WATER_TABLE[kind]
    ts = np.array([r[0] for r in table])
    t = float(np.clip(temp_c, ts[0], ts[-1]))
    rho = float(np.interp(t, ts, [r[1] for r in table]))
    nu = float(np.interp(t, ts, [r[2] for r in table]))
    return rho, nu


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
AXES = {"x": 0, "y": 1, "z": 2}


def orientation_matrix(points, long_axis, nose, up_axis):
    """Rotation R (x' = R x) mapping the lure's long axis to +x with the nose
    at min x (upstream; flow is +x) and the chosen up axis to +z."""
    ext = points.max(axis=0) - points.min(axis=0)
    if long_axis == "auto":
        li = int(np.argmax(ext))
    else:
        li = AXES[long_axis]
    e_long = np.zeros(3)
    # Nose at the 'min' end of the long axis -> body runs from nose (-) to
    # tail (+) along +long; that direction must become +x.
    e_long[li] = 1.0 if nose == "min" else -1.0

    others = [i for i in range(3) if i != li]
    if up_axis == "auto":
        a, b = others
        # Thinnest remaining dimension is "up" (flat spoons swim flat);
        # near-ties (round bodies) prefer the original z, then y.
        if abs(ext[a] - ext[b]) <= 0.05 * max(ext[a], ext[b], 1e-30):
            ui = 2 if 2 in others else 1
        else:
            ui = a if ext[a] < ext[b] else b
        e_up = np.zeros(3)
        e_up[ui] = 1.0
    else:
        sign = -1.0 if up_axis.startswith("-") else 1.0
        ui = AXES[up_axis[-1]]
        if ui == li:
            raise SystemExit("--up-axis must differ from the long axis")
        e_up = np.zeros(3)
        e_up[ui] = sign

    e_side = np.cross(e_up, e_long)  # becomes +y (right-handed x,y,z)
    R = np.vstack([e_long, e_side, e_up])  # rows: new axes in old coords
    assert abs(np.linalg.det(R) - 1.0) < 1e-9
    return R, dict(
        long_axis="xyz"[li],
        nose=nose,
        up_axis_index=int(ui),
        up_axis=("-" if e_up[ui] < 0 else "") + "xyz"[ui],
        extents_before=ext.tolist(),
    )


def ray_hit_distances(origin, direction, tris):
    """Moller-Trumbore ray/triangle intersection, vectorised over triangles.
    Returns the (unsorted) distances t > 0 of all hits."""
    d = np.asarray(direction, dtype=float)
    v0 = tris[:, 0, :]
    e1 = tris[:, 1, :] - v0
    e2 = tris[:, 2, :] - v0
    pvec = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, pvec)
    ok = np.abs(det) > 1e-30
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tvec = np.asarray(origin, dtype=float) - v0
    u = np.einsum("ij,ij->i", tvec, pvec) * inv
    qvec = np.cross(tvec, e1)
    v = (qvec @ d) * inv
    t = np.einsum("ij,ij->i", e2, qvec) * inv
    eps = 1e-12
    hit = ok & (u >= -eps) & (v >= -eps) & (u + v <= 1 + eps) & (t > 1e-12)
    return t[hit]


def point_inside(point, tris):
    """Parity test with a slightly skewed ray (avoids edge/vertex hits)."""
    d = np.array([1.0, 1.0e-3 * math.sqrt(2.0), 1.0e-3 * math.sqrt(3.0)])
    d /= np.linalg.norm(d)
    return len(ray_hit_distances(point, d, tris)) % 2 == 1


def classify_components(mesh):
    """Split into connected components: outer shells (V>0), sealed internal
    cavities (V<0, e.g. rattle chambers) and dropped slivers."""
    parts = mesh.split(only_watertight=False)
    if len(parts) == 0:
        parts = [mesh]
    vols = np.array([p.volume for p in parts])
    total = float(np.sum(np.abs(vols))) or 1.0
    outer, cavities, dropped = [], [], []
    for p, v in zip(parts, vols):
        if abs(v) < 1e-4 * total or len(p.faces) < 4:
            dropped.append(p)
        elif v > 0:
            outer.append(p)
        else:
            cavities.append(p)
    if not outer:
        raise SystemExit(
            "No outward-oriented closed shell found in the STL "
            "(all components have negative volume?)"
        )
    # A negative shell that is not enclosed by any outer shell is an inverted
    # outer shell (bad winding) -> flip it.
    really_cav = []
    for c in cavities:
        probe = c.vertices[0]
        if any(point_inside(probe, o.triangles) for o in outer):
            really_cav.append(c)
        else:
            c = c.copy()
            c.invert()
            outer.append(c)
    return outer, really_cav, dropped


# --------------------------------------------------------------------------- #
# Voxelisation (pure numpy ray parity) and printed mass model
# --------------------------------------------------------------------------- #
def voxelize(tris, h, bounds):
    """Inside/outside voxel mask by ray parity along +x for every (y,z) column.
    Works for multiple shells and internal cavities (parity), needs no rtree.
    Returns (mask[nx,ny,nz], (x0, y0, z0)) with voxel centres x0 + i*h ..."""
    lo = np.asarray(bounds[0], dtype=float) - 1.5 * h
    hi = np.asarray(bounds[1], dtype=float) + 1.5 * h
    n = np.maximum(np.ceil((hi - lo) / h).astype(int), 1)
    # Irrational sub-cell offsets keep rays away from mesh edges/vertices.
    off = np.array([0.5, 0.5 + 0.0123456789, 0.5 + 0.0234567891])
    x0, y0, z0 = lo + off * h
    nx, ny, nz = (int(v) for v in n)

    P = tris[:, :, 1:]  # (F,3,2) y,z of the vertices
    ymin, ymax = P[:, :, 0].min(1), P[:, :, 0].max(1)
    zmin, zmax = P[:, :, 1].min(1), P[:, :, 1].max(1)
    iy0 = np.ceil((ymin - y0) / h).astype(int)
    iy1 = np.floor((ymax - y0) / h).astype(int)
    iz0 = np.ceil((zmin - z0) / h).astype(int)
    iz1 = np.floor((zmax - z0) / h).astype(int)
    iy0, iz0 = np.maximum(iy0, 0), np.maximum(iz0, 0)
    iy1, iz1 = np.minimum(iy1, ny - 1), np.minimum(iz1, nz - 1)
    ky = iy1 - iy0 + 1
    kz = iz1 - iz0 + 1
    a = P[:, 1] - P[:, 0]
    b = P[:, 2] - P[:, 0]
    den = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    valid = (ky > 0) & (kz > 0) & (np.abs(den) > 1e-30)

    cols_all, x_all = [], []
    keys = ky[valid] * 100000 + kz[valid]
    idx_valid = np.nonzero(valid)[0]
    for key in np.unique(keys):
        sel = idx_valid[keys == key]
        kyy, kzz = int(key // 100000), int(key % 100000)
        jy = iy0[sel][:, None, None] + np.arange(kyy)[None, :, None]
        jz = iz0[sel][:, None, None] + np.arange(kzz)[None, None, :]
        jy, jz = np.broadcast_arrays(jy, jz)
        qy = y0 + jy * h - P[sel, 0, 0][:, None, None]
        qz = z0 + jz * h - P[sel, 0, 1][:, None, None]
        aa, bb, dd = a[sel], b[sel], den[sel]
        w1 = (qy * bb[:, None, None, 1] - qz * bb[:, None, None, 0]) / dd[:, None, None]
        w2 = (aa[:, None, None, 0] * qz - aa[:, None, None, 1] * qy) / dd[:, None, None]
        w0 = 1.0 - w1 - w2
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        X = tris[sel, :, 0]
        xs = (
            w0 * X[:, 0, None, None]
            + w1 * X[:, 1, None, None]
            + w2 * X[:, 2, None, None]
        )
        cols_all.append((jy * nz + jz)[inside])
        x_all.append(xs[inside])

    mask = np.zeros((ny * nz, nx), dtype=bool)
    if not cols_all:
        return mask.reshape(ny, nz, nx).transpose(2, 0, 1), (x0, y0, z0), 0
    cols = np.concatenate(cols_all)
    xs = np.concatenate(x_all)
    order = np.lexsort((xs, cols))
    cols, xs = cols[order], xs[order]
    # Pair consecutive crossings within each column.
    ucols, start, counts = np.unique(cols, return_index=True, return_counts=True)
    odd = counts % 2 == 1
    n_odd = int(odd.sum())
    rank = np.arange(len(cols)) - np.repeat(start, counts)
    keep = ~np.repeat(odd, counts)  # skip columns with inconsistent parity
    first = keep & (rank % 2 == 0)
    second = keep & (rank % 2 == 1)
    c_pair = cols[first]
    xa, xb = xs[first], xs[second]
    ia = np.clip(np.ceil((xa - x0) / h).astype(int), 0, nx)
    ib = np.clip(np.ceil((xb - x0) / h).astype(int), 0, nx)
    diff = np.zeros((ny * nz, nx + 1), dtype=np.int32)
    np.add.at(diff, (c_pair, ia), 1)
    np.add.at(diff, (c_pair, ib), -1)
    mask = np.cumsum(diff, axis=1)[:, :nx] > 0
    return mask.reshape(ny, nz, nx).transpose(2, 0, 1), (x0, y0, z0), n_odd


def grid_moments(dens, h, origin):
    """Mass, CoM and inertia (about CoM) of a voxel density field."""
    x0, y0, z0 = origin
    nx, ny, nz = dens.shape
    xs = x0 + h * np.arange(nx)
    ys = y0 + h * np.arange(ny)
    zs = z0 + h * np.arange(nz)
    dv = h**3
    Mx = dens.sum(axis=(1, 2)) * dv
    My = dens.sum(axis=(0, 2)) * dv
    Mz = dens.sum(axis=(0, 1)) * dv
    m = float(Mx.sum())
    if m <= 0:
        raise SystemExit("Voxel model has zero mass - check the STL/units")
    c = np.array([xs @ Mx, ys @ My, zs @ Mz]) / m
    Sxx = (xs**2) @ Mx
    Syy = (ys**2) @ My
    Szz = (zs**2) @ Mz
    Sxy = xs @ (dens.sum(axis=2) * dv) @ ys
    Sxz = xs @ (dens.sum(axis=1) * dv) @ zs
    Syz = ys @ (dens.sum(axis=0) * dv) @ zs
    S = np.array([[Sxx, Sxy, Sxz], [Sxy, Syy, Syz], [Sxz, Syz, Szz]])
    S -= m * np.outer(c, c)  # second moments about the CoM
    inertia = np.trace(S) * np.eye(3) - S
    inertia += m * h * h / 6.0 * np.eye(3)  # self-inertia of each voxel cube
    return m, c, inertia


def surface_second_moments(mesh):
    """Area, first and second area moments of a triangulated surface."""
    tris = mesh.triangles
    area = mesh.area_faces
    A = float(area.sum())
    cen = tris.mean(axis=1)
    first = (area[:, None] * cen).sum(axis=0)
    ssum = tris.sum(axis=1)
    # int_T r r^T dA = A/12 * (sum_i v_i v_i^T + s s^T), s = sum_i v_i
    vv = np.einsum("fij,fik->fjk", tris, tris)
    S = (area[:, None, None] / 12.0 * (vv + np.einsum("fj,fk->fjk", ssum, ssum))).sum(0)
    return A, first, S


def inertia_from_moments(m, first, S_origin):
    c = first / m
    S = S_origin - m * np.outer(c, c)
    return c, np.trace(S) * np.eye(3) - S


def principal_frame(inertia):
    """Principal moments and axes (columns), ordered/signed to be close to the
    global axes, right-handed."""
    lam, E = np.linalg.eigh(0.5 * (inertia + inertia.T))
    order = []
    remaining = [0, 1, 2]
    for ax in range(3):
        j = max(remaining, key=lambda k: abs(E[ax, k]))
        order.append(j)
        remaining.remove(j)
    lam = lam[order]
    E = E[:, order]
    for k in range(3):
        if E[k, k] < 0:
            E[:, k] *= -1.0
    if np.linalg.det(E) < 0:
        E[:, 2] *= -1.0
    return lam, E


# --------------------------------------------------------------------------- #
# Template handling and checks
# --------------------------------------------------------------------------- #
def strip_foam_comments_and_strings(text: str) -> str:
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def check_foam_text(text: str):
    """Return a list of problems: leftover tokens, unbalanced brackets."""
    problems = []
    toks = sorted(set(TOKEN_RE.findall(text)))
    if toks or "@@" in text:
        problems.append(f"leftover placeholder(s): {toks or ['@@']}")
    body = strip_foam_comments_and_strings(text)
    stack = []
    pairs = {")": "(", "}": "{"}
    for k, ch in enumerate(body):
        if ch in "({":
            stack.append(ch)
        elif ch in ")}":
            if not stack or stack[-1] != pairs[ch]:
                problems.append(f"unbalanced '{ch}' near char {k}")
                return problems
            stack.pop()
    if stack:
        problems.append(f"unclosed '{stack[-1]}' ({len(stack)} open)")
    return problems


def is_text_dict(path: Path) -> bool:
    if path.suffix.lower() in {".stl", ".json", ".md", ".png", ".gz"}:
        return False
    try:
        head = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\0" not in head


def check_case_dir(case: Path):
    """Check all OpenFOAM dictionaries in a case (and leftover tokens
    everywhere). Returns {relative path: [problems]} for files with issues."""
    issues = {}
    for p in sorted(case.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(case))
        if p.name in ("Allrun", "Allclean") or p.suffix in (".md", ".json"):
            txt = p.read_text(errors="replace")
            if TOKEN_RE.search(txt):
                issues[rel] = ["leftover placeholder"]
            continue
        if not is_text_dict(p):
            continue
        txt = p.read_text(errors="replace")
        prob = check_foam_text(txt)
        if prob:
            issues[rel] = prob
    return issues


def fill_tokens(case: Path, tokens: dict, keep_buoyancy: bool):
    for p in sorted(case.rglob("*")):
        if not p.is_file() or not is_text_dict(p) or p.suffix in (".md", ".json"):
            continue
        txt = p.read_text()
        if "@@" not in txt:
            continue
        # Optional blocks delimited by //@@NAME_BEGIN@@ ... //@@NAME_END@@
        blk = re.compile(
            r"^[ \t]*//@@BUOYANCY_BEGIN@@[ \t]*\n(.*?)^[ \t]*//@@BUOYANCY_END@@[ \t]*\n",
            re.S | re.M,
        )
        if keep_buoyancy:
            txt = blk.sub(lambda m: m.group(1), txt)
        else:
            txt = blk.sub("        // (gravity/buoyancy disabled: --no-gravity)\n", txt)

        def rep(m, path=p):
            key = m.group(0)[2:-2]
            if key not in tokens:
                raise SystemExit(f"{path}: no value for token {m.group(0)}")
            return str(tokens[key])

        txt = TOKEN_RE.sub(rep, txt)
        p.write_text(txt)


def write_stl(path: Path, mesh, ascii_stl: bool = False, name: str = "lure"):
    tris = np.asarray(mesh.triangles, dtype=float)
    normals = np.asarray(mesh.face_normals, dtype=float)
    path.parent.mkdir(parents=True, exist_ok=True)
    if ascii_stl:
        with open(path, "w") as f:
            f.write(f"solid {name}\n")
            for nrm, tri in zip(normals, tris):
                f.write(
                    f"  facet normal {nrm[0]:.6e} {nrm[1]:.6e} {nrm[2]:.6e}\n"
                    "    outer loop\n"
                )
                for v in tri:
                    f.write(f"      vertex {v[0]:.9e} {v[1]:.9e} {v[2]:.9e}\n")
                f.write("    endloop\n  endfacet\n")
            f.write(f"endsolid {name}\n")
    else:
        # Header must not start with 'solid' (would look like ASCII STL).
        header = f"binary STL '{name}' (metres) written by prepare_case.py"
        header = header.encode("ascii")[:80].ljust(80, b" ")
        rec = np.zeros(
            len(tris), dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")]
        )
        rec["n"] = normals
        rec["v"] = tris
        with open(path, "wb") as f:
            f.write(header)
            f.write(np.uint32(len(tris)).tobytes())
            f.write(rec.tobytes())


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(
        description="Prepare an OpenFOAM v2412 overset 6-DoF case for a towed lure "
        "(does not run OpenFOAM).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("stl", help="lure STL file (ASCII or binary)")
    p.add_argument(
        "-o",
        "--out",
        default=None,
        help="output case directory (default: ./<stl-stem>_case)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="replace an existing output directory that was generated "
        "by this script (contains case_info.json)",
    )

    g = p.add_argument_group("geometry / orientation")
    g.add_argument(
        "--units",
        choices=sorted(UNIT_SCALE),
        default="mm",
        help="units of the STL coordinates",
    )
    g.add_argument(
        "--long-axis",
        choices=["auto", "x", "y", "z"],
        default="auto",
        help="STL axis along the lure body (auto = largest extent)",
    )
    g.add_argument(
        "--nose",
        choices=["min", "max"],
        default="min",
        help="which end of the long axis is the nose (faces upstream)",
    )
    g.add_argument(
        "--up-axis",
        choices=["auto", "x", "y", "z", "-x", "-y", "-z"],
        default="auto",
        help="STL axis that should point up (+z). auto: thinnest "
        "remaining dimension, ties -> z",
    )
    g.add_argument(
        "--rotate-deg",
        type=float,
        nargs=3,
        metavar=("RX", "RY", "RZ"),
        default=None,
        help="extra rotation applied to the STL first (about x, then "
        "y, then z, degrees)",
    )

    m = p.add_argument_group("mass properties (printed part)")
    m.add_argument(
        "--density",
        type=float,
        default=1240.0,
        help="filament density kg/m3 (PLA 1240, PETG 1270, ABS 1040)",
    )
    m.add_argument(
        "--infill", type=float, default=0.20, help="infill volume fraction 0..1"
    )
    m.add_argument(
        "--wall-mm",
        type=float,
        default=1.2,
        help="solid shell thickness (perimeters, top/bottom) in mm",
    )
    m.add_argument(
        "--mass-g",
        type=float,
        default=None,
        help="measured mass of the printed lure in grams (keeps the "
        "shell/infill distribution, rescales its magnitude)",
    )
    m.add_argument(
        "--ballast-g",
        type=float,
        default=0.0,
        help="point ballast mass in grams (e.g. lead/steel insert)",
    )
    m.add_argument(
        "--ballast-pos",
        default=None,
        help="ballast position x,y,z in ORIGINAL STL coordinates/units",
    )
    m.add_argument(
        "--mass-model",
        choices=["voxel", "surface"],
        default="voxel",
        help="voxel: distance-transform shell (needs scipy); surface: "
        "thin-shell approximation",
    )
    m.add_argument(
        "--voxel-mm",
        type=float,
        default=None,
        help="voxel size for the mass model (default: wall/4, <= L/250)",
    )

    r = p.add_argument_group("rigging / leader")
    r.add_argument(
        "--tow-point",
        default="auto",
        help="'auto' (front-most point on the body centre line) or "
        "x,y,z in ORIGINAL STL coordinates/units",
    )
    r.add_argument(
        "--rigging",
        choices=["eye", "line-through"],
        default="eye",
        help="eye: leader tied to a tow eye; line-through: leader runs "
        "through the body (give the line ENTRY point as "
        "--tow-point)",
    )
    r.add_argument("--leader-m", type=float, default=1.2, help="leader length (m)")
    r.add_argument(
        "--leader-ea",
        type=float,
        default=400.0,
        help="leader axial stiffness E*A in N (k = EA/length); "
        "~300-500 N for 15-25 lb nylon mono",
    )
    r.add_argument(
        "--leader-stiffness",
        type=float,
        default=None,
        help="spring stiffness in N/m (overrides --leader-ea)",
    )
    r.add_argument(
        "--leader-damping-ratio",
        type=float,
        default=0.3,
        help="axial damping ratio of the leader spring",
    )
    r.add_argument(
        "--line-angle-deg",
        type=float,
        default=None,
        help="initial leader elevation in degrees (+ = boat-side end "
        "above the lure). Default: from estimated drag and net "
        "weight",
    )
    r.add_argument(
        "--line-azimuth-deg",
        type=float,
        default=0.0,
        help="initial leader azimuth (+ = boat-side end towards +y)",
    )
    r.add_argument(
        "--cd-estimate",
        type=float,
        default=0.8,
        help="drag coefficient (frontal area) used only to place the "
        "anchor near equilibrium",
    )

    f = p.add_argument_group("flow")
    f.add_argument("--speed-mph", type=float, default=2.5, help="trolling speed")
    f.add_argument("--water", choices=["fresh", "salt"], default="fresh")
    f.add_argument("--water-temp-c", type=float, default=15.0)
    f.add_argument(
        "--no-gravity",
        action="store_true",
        help="neutral-buoyancy idealisation: no weight, no buoyancy",
    )
    f.add_argument(
        "--turbulence",
        choices=["kOmegaSST", "kOmegaSSTDDES", "laminar"],
        default="kOmegaSST",
    )
    f.add_argument(
        "--turbulence-intensity",
        type=float,
        default=0.02,
        help="inflow turbulence intensity (k = 1.5 (I U)^2)",
    )
    f.add_argument(
        "--eddy-viscosity-ratio",
        type=float,
        default=10.0,
        help="inflow nut/nu (sets omega)",
    )
    f.add_argument(
        "--ramp-time",
        type=float,
        default=0.2,
        help="smooth start-up ramp of the inflow (s); 0 = impulsive",
    )
    f.add_argument(
        "--fluctuation-percent",
        type=float,
        default=0.0,
        help="bounded inflow fluctuation amplitude, %% of tow speed",
    )
    f.add_argument(
        "--fluctuation-period",
        type=float,
        default=1.0,
        help="characteristic period of the fluctuations (s)",
    )
    f.add_argument(
        "--fluctuation-lateral",
        type=float,
        default=0.5,
        help="lateral/vertical fluctuation amplitude relative to the streamwise one",
    )
    f.add_argument("--seed", type=int, default=1, help="fluctuation random seed")

    n = p.add_argument_group("mesh / numerics")
    n.add_argument("--mesh-level", choices=sorted(MESH_PRESETS), default="medium")
    n.add_argument(
        "--envelope",
        type=float,
        default=1.0,
        help="lateral motion envelope refined in the background "
        "(lure lengths, each side)",
    )
    n.add_argument(
        "--vertical-envelope",
        type=float,
        default=None,
        help="vertical envelope (lure lengths). Default: from the "
        "line-angle uncertainty, between --envelope and 3",
    )
    n.add_argument(
        "--max-tilt-deg",
        type=float,
        default=30.0,
        help="yaw/pitch swept when sizing the refined motion box",
    )
    n.add_argument("--end-time", type=float, default=4.0, help="simulated time (s)")
    n.add_argument(
        "--write-interval",
        type=float,
        default=0.05,
        help="full-field write interval (s)",
    )
    n.add_argument(
        "--surface-interval",
        type=float,
        default=0.01,
        help="lure-surface (VTK) write interval for animations (s)",
    )
    n.add_argument("--max-co", type=float, default=2.0, help="maximum Courant number")
    n.add_argument(
        "--ddt", choices=["Euler", "backward"], default="Euler", help="time scheme"
    )
    n.add_argument("--n-outer", type=int, default=2, help="PIMPLE outer correctors")
    n.add_argument(
        "--accel-relax",
        type=float,
        default=None,
        help="6-DoF accelerationRelaxation (default from the added-mass ratio)",
    )
    n.add_argument(
        "--accel-damp",
        type=float,
        default=1.0,
        help="6-DoF accelerationDamping (1 = none)",
    )
    n.add_argument(
        "--nprocs",
        type=int,
        default=4,
        help="numberOfSubdomains written to decomposeParDict (Allrun -np N overrides)",
    )
    n.add_argument(
        "--ascii-stl",
        action="store_true",
        help="write the case STL as ASCII instead of binary",
    )
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    notes = []

    def note(msg):
        notes.append(msg)
        print(f"  NOTE: {msg}")

    stl_path = Path(a.stl).expanduser().resolve()
    if not stl_path.is_file():
        raise SystemExit(f"STL not found: {stl_path}")
    out = Path(a.out or f"{stl_path.stem}_case").expanduser().resolve()
    if not TEMPLATE_DIR.is_dir():
        raise SystemExit(f"template directory missing: {TEMPLATE_DIR}")
    if not (0.0 <= a.infill <= 1.0):
        raise SystemExit("--infill must be within 0..1")
    if a.leader_m <= 0 or a.speed_mph <= 0 or a.end_time <= 0:
        raise SystemExit("--leader-m, --speed-mph and --end-time must be > 0")

    print(f"[1/8] Loading {stl_path}")
    raw = trimesh.load(str(stl_path), force="mesh", process=True)
    if not isinstance(raw, trimesh.Trimesh) or len(raw.faces) == 0:
        raise SystemExit("could not read a triangle mesh from the STL")
    if not raw.is_watertight:
        trimesh.repair.fill_holes(raw)
        trimesh.repair.fix_normals(raw)
        if not raw.is_watertight:
            raise SystemExit(
                "STL is not watertight; repair it (e.g. in OpenSCAD/"
                "MeshLab) - mass properties need a closed volume"
            )
        note("STL was not watertight; small holes were filled automatically")
    print(f"      {len(raw.faces)} triangles, watertight={raw.is_watertight}")

    # ------------------------------------------------------------------ #
    print("[2/8] Scaling and orienting (flow +x, nose upstream, up +z)")
    s = UNIT_SCALE[a.units]
    R_user = np.eye(3)
    if a.rotate_deg is not None:
        rx, ry, rz = (math.radians(v) for v in a.rotate_deg)
        R_user = rot_z(rz) @ rot_y(ry) @ rot_x(rx)
    pts = (raw.vertices * s) @ R_user.T
    R_or, orient_info = orientation_matrix(pts, a.long_axis, a.nose, a.up_axis)
    R = R_or @ R_user
    verts = (raw.vertices * s) @ R.T
    mesh = trimesh.Trimesh(vertices=verts, faces=raw.faces.copy(), process=False)

    outer_parts, cavities, dropped = classify_components(mesh)
    lo = np.min([p.bounds[0] for p in outer_parts], axis=0)
    hi = np.max([p.bounds[1] for p in outer_parts], axis=0)
    t_vec = np.array([-lo[0], -0.5 * (lo[1] + hi[1]), -0.5 * (lo[2] + hi[2])])

    def to_case(p_stl):
        """ORIGINAL STL coordinates/units -> case coordinates (m)."""
        return R @ (np.asarray(p_stl, dtype=float) * s) + t_vec

    for part in outer_parts + cavities:
        part.apply_translation(t_vec)
    # wetted outer surface (CFD) and printed volume (cavities subtracted)
    outer = trimesh.util.concatenate([p.copy() for p in outer_parts])
    solid = trimesh.util.concatenate([p.copy() for p in outer_parts + cavities])
    lo, hi = outer.bounds
    L = float(hi[0] - lo[0])
    half_y = float(max(abs(lo[1]), abs(hi[1])))
    half_z = float(max(abs(lo[2]), abs(hi[2])))
    R_body = max(half_y, half_z)
    print(
        f"      length {L * 1e3:.1f} mm, width {2 * half_y * 1e3:.1f} mm, "
        f"height {2 * half_z * 1e3:.1f} mm; shells: {len(outer_parts)} outer, "
        f"{len(cavities)} sealed cavity(ies), {len(dropped)} sliver(s) dropped"
    )
    if not (0.02 <= L <= 0.4):
        note(f"lure length {L * 1e3:.0f} mm is outside 20-400 mm - check --units")

    # ------------------------------------------------------------------ #
    print("[3/8] Mass properties (shell + infill)")
    rho_mat = a.density
    wall = a.wall_mm * 1e-3
    vol_solid = float(solid.volume)
    vol_disp = float(outer.volume)
    cob = np.asarray(outer.center_mass, dtype=float)
    exact = solid.mass_properties  # uniform density 1 -> scale below
    exact_m = rho_mat * float(exact["volume"])
    exact_c = np.asarray(exact["center_mass"], dtype=float)
    exact_I = rho_mat * np.asarray(exact["inertia"], dtype=float)

    h_vox = a.voxel_mm * 1e-3 if a.voxel_mm else min(wall / 4.0, L / 250.0)
    ext = hi - lo
    while np.prod(np.ceil(ext / h_vox) + 4) > 2.5e7:
        h_vox *= 1.25
    occ, origin, n_odd = voxelize(solid.triangles, h_vox, solid.bounds)
    if n_odd:
        note(f"voxeliser skipped {n_odd} ray column(s) with odd crossing count")
    vox_vol = float(occ.sum()) * h_vox**3
    print(
        f"      voxel size {h_vox * 1e3:.3f} mm, grid {occ.shape}, voxel volume "
        f"{vox_vol * 1e6:.3f} cm3 vs exact {vol_solid * 1e6:.3f} cm3"
    )

    mass_model = a.mass_model
    if mass_model == "voxel" and _ndimage is None:
        note("scipy not available - falling back to --mass-model surface")
        mass_model = "surface"
    if mass_model == "voxel":
        dist = _ndimage.distance_transform_edt(occ, sampling=h_vox)
        shell = occ & (dist < wall + 0.5 * h_vox)
        dens = np.where(shell, rho_mat, rho_mat * a.infill) * occ
        m_p, c_p, I_p = grid_moments(dens, h_vox, origin)
        m_full, c_full, I_full = grid_moments(occ * rho_mat, h_vox, origin)
        v_shell = float(shell.sum()) * h_vox**3
        # Calibrate the voxel model against the exact solid (removes the
        # voxelisation bias of a few per cent in mass/inertia).
        fm = exact_m / m_full
        m_p *= fm
        I_p *= fm
        c_p = c_p + (exact_c - c_full)
        check = dict(
            voxel_vs_exact_mass_ratio=float(1.0 / fm),
            voxel_vs_exact_com_offset_mm=float(np.linalg.norm(c_full - exact_c) * 1e3),
        )
    else:
        A_s, first_s, S_s = surface_second_moments(solid)
        v_shell = min(A_s * wall, vol_solid)
        k_shell = v_shell / (A_s * wall) if A_s > 0 else 0.0
        # thin shell (density rho, thickness wall) and uniform solid moments
        m_sh = rho_mat * wall * A_s * k_shell
        first_sh = rho_mat * wall * first_s * k_shell
        S_sh = rho_mat * wall * S_s * k_shell
        S_solid = exact_I.copy()
        # solid second moments about origin: S = (tr(I)/2) I - I + m c c^T
        S_solid = (
            0.5 * np.trace(exact_I) * np.eye(3)
            - exact_I
            + exact_m * np.outer(exact_c, exact_c)
        )
        m_p = a.infill * exact_m + (1 - a.infill) * m_sh
        first = a.infill * exact_m * exact_c + (1 - a.infill) * first_sh
        S_o = a.infill * S_solid + (1 - a.infill) * S_sh
        c_p, I_p = inertia_from_moments(m_p, first, S_o)
        check = dict(shell_area_m2=A_s)
    shell_frac = v_shell / vol_solid if vol_solid > 0 else 0.0

    if a.mass_g is not None:
        fm = (a.mass_g * 1e-3) / m_p
        note(f"mass rescaled to measured {a.mass_g:.2f} g (factor {fm:.3f})")
        m_p *= fm
        I_p *= fm

    m_ball = max(a.ballast_g, 0.0) * 1e-3
    r_ball = None
    if m_ball > 0:
        if not a.ballast_pos:
            raise SystemExit("--ballast-g needs --ballast-pos x,y,z")
        r_ball = to_case(parse_xyz(a.ballast_pos, "--ballast-pos"))
        if not point_inside(r_ball, solid.triangles):
            note("ballast position is not inside the printed solid")
    M = m_p + m_ball
    com = (m_p * c_p + (m_ball * r_ball if m_ball > 0 else 0.0)) / M
    d_p = c_p - com
    I = I_p + m_p * (d_p @ d_p * np.eye(3) - np.outer(d_p, d_p))
    if m_ball > 0:
        d_b = r_ball - com
        I += m_ball * (d_b @ d_b * np.eye(3) - np.outer(d_b, d_b))
    I_princ, E = principal_frame(I)
    print(
        f"      printed mass {m_p * 1e3:.2f} g (shell {shell_frac * 100:.0f}% of "
        f"volume), ballast {m_ball * 1e3:.2f} g, total {M * 1e3:.2f} g"
    )
    print(f"      CoM {fvec(com * 1e3, 5)} mm; principal I {fvec(I_princ, 4)} kg m2")

    # ------------------------------------------------------------------ #
    print("[4/8] Flow and hydrostatics")
    rho_w, nu = water_properties(a.water, a.water_temp_c)
    U = a.speed_mph * MPH_TO_MS
    Re = U * L / nu
    gmag = 0.0 if a.no_gravity else G0
    B = rho_w * vol_disp * G0
    W = M * G0
    W_net = (W - B) if not a.no_gravity else 0.0
    proj = occ.any(axis=0)
    A_front = float(proj.sum()) * h_vox**2
    D_est = 0.5 * rho_w * U * U * a.cd_estimate * A_front
    K_roll = B * (cob[2] - com[2])
    # Lateral added mass (strip theory, circle/plate of the max section width)
    occ_y = occ.any(axis=2)
    occ_z = occ.any(axis=1)
    wy = occ_y.sum(axis=1) * h_vox
    wz = occ_z.sum(axis=1) * h_vox
    m_added = float(rho_w * math.pi / 4.0 * np.sum(np.maximum(wy, wz) ** 2) * h_vox)
    added_ratio = m_added / M
    a_relax = (
        a.accel_relax
        if a.accel_relax is not None
        else float(np.clip(round(1.0 / (1.0 + added_ratio), 2), 0.15, 0.9))
    )
    print(
        f"      U = {U:.4f} m/s, Re_L = {Re:.3g}, water {a.water} "
        f"{a.water_temp_c:g} C (rho {rho_w:.1f}, nu {nu:.3e})"
    )
    print(
        f"      displaced {vol_disp * 1e6:.2f} cm3, buoyancy {B:.4f} N, weight "
        f"{W:.4f} N -> net {'down' if W - B > 0 else 'up'} {abs(W - B):.4f} N"
        + ("  (gravity OFF)" if a.no_gravity else "")
    )
    print(
        f"      frontal area {A_front * 1e4:.3f} cm2, est. drag {D_est:.3f} N "
        f"(Cd {a.cd_estimate}); CoB-CoM height {1e3 * (cob[2] - com[2]):+.2f} mm "
        f"-> hydrostatic roll stiffness {K_roll:.2e} N m/rad"
    )
    print(
        f"      lateral added mass ~{m_added * 1e3:.1f} g (ratio {added_ratio:.2f})"
        f" -> accelerationRelaxation {a_relax}"
    )
    if K_roll < 0 and not a.no_gravity:
        note(
            "centre of buoyancy is below the centre of mass: hydrostatically "
            "unstable in roll (will tend to flip / roll freely)"
        )

    # ------------------------------------------------------------------ #
    print("[5/8] Tow point and leader")
    tris_outer = outer.triangles
    if a.tow_point.strip().lower() == "auto":
        tow = None
        for yc, zc in ((0.0, 0.0), (cob[1], cob[2])):
            origin_ray = np.array([lo[0] - L, yc, zc])
            t_hit = ray_hit_distances(origin_ray, np.array([1.0, 0.0, 0.0]), tris_outer)
            if len(t_hit):
                tow = origin_ray + np.array([t_hit.min(), 0.0, 0.0])
                break
        if tow is None:
            tow = outer.vertices[np.argmin(outer.vertices[:, 0])].copy()
            note("centre-line ray missed the body; tow point = front-most vertex")
        tow_src = "auto (front-most point on the body centre line)"
        if a.rigging == "line-through":
            note(
                "line-through rigging with --tow-point auto: pass the point where "
                "the line ENTERS the body (channel mouth), e.g. for "
                "king_salmon_cut_plug.scad: --tow-point 25,0,-4"
            )
    else:
        tow = to_case(parse_xyz(a.tow_point, "--tow-point"))
        tow_src = f"user ({a.tow_point} {a.units} in STL coordinates)"
        try:
            samples, _ = trimesh.sample.sample_surface(outer, 200000, seed=0)
        except TypeError:  # older trimesh without 'seed'
            samples, _ = trimesh.sample.sample_surface(outer, 200000)
        dmin = float(np.min(np.linalg.norm(samples - tow, axis=1)))
        where = (
            "inside the printed solid"
            if point_inside(tow, solid.triangles)
            else "in the water"
        )
        print(f"      user tow point is {dmin * 1e3:.2f} mm from the surface ({where})")
        if dmin > max(0.02 * L, 0.002):
            note(
                f"tow point is {dmin * 1e3:.1f} mm from the lure surface ({where}); "
                "use the eye position or, for line-through rigging, the channel "
                "mouth where the line enters the body"
            )
    if a.line_angle_deg is not None:
        elev = math.radians(a.line_angle_deg)
        elev_src = "user"
    else:
        elev = math.atan2(W_net, max(D_est, 1e-12))
        elev_src = "estimated from net weight and drag"
    azim = math.radians(a.line_azimuth_deg)
    d_hat = np.array(
        [
            -math.cos(elev) * math.cos(azim),
            math.cos(elev) * math.sin(azim),
            math.sin(elev),
        ]
    )
    anchor = tow + a.leader_m * d_hat
    k_leader = a.leader_stiffness if a.leader_stiffness else a.leader_ea / a.leader_m
    c_leader = a.leader_damping_ratio * 2.0 * math.sqrt(k_leader * M)
    T_spring = 2.0 * math.pi * math.sqrt(M / k_leader)

    def elev_for(cd):
        return math.atan2(W_net, max(0.5 * rho_w * U * U * cd * A_front, 1e-12))

    dz_unc = (
        0.5
        * a.leader_m
        * abs(
            math.sin(elev_for(a.cd_estimate / 1.5))
            - math.sin(elev_for(a.cd_estimate * 1.5))
        )
    )
    print(f"      tow point {fvec(tow * 1e3, 5)} mm [{tow_src}]")
    print(
        f"      leader {a.leader_m} m, elevation {math.degrees(elev):+.1f} deg "
        f"({elev_src}), k = {k_leader:.1f} N/m, c = {c_leader:.3f} N s/m, "
        f"axial period {T_spring * 1e3:.1f} ms"
    )

    buoy_H = 1.0e4  # m - height of the virtual buoyancy anchor
    buoy_anchor = cob + np.array([0.0, 0.0, buoy_H])
    k_buoy = B / buoy_H

    # ------------------------------------------------------------------ #
    print("[6/8] Mesh layout")
    preset = MESH_PRESETS[a.mesh_level]
    h_c = L / preset["bg_cells_per_L"]
    h0 = h_c * 2**N_BG_LEVELS
    smin, smax = preset["surf"]
    n_layers = preset["layers"]

    # Component box (moves with the lure)
    side = R_body + max(0.2 * L, R_body)
    ncx = int(math.ceil((1.75 * L) / h_c))
    cx0 = -0.25 * L
    cx1 = cx0 + ncx * h_c
    ncs = int(math.ceil(2.0 * side / h_c))
    side = 0.5 * ncs * h_c
    cbox_lo = np.array([cx0, -side, -side])
    cbox_hi = np.array([cx1, side, side])
    loc_in_mesh = cbox_lo + np.array([0.37, 0.41, 0.43]) * h_c
    wake_lo = np.array([L - 0.25 * L, -0.5 * (R_body + side), -0.5 * (R_body + side)])
    wake_hi = np.array([cx1 - h_c, 0.5 * (R_body + side), 0.5 * (R_body + side)])
    h_l = [h_c / 2**k for k in range(smax + 1)]
    l1, l2 = max(smin - 1, 0), max(smin - 2, 0)
    d1 = 4.0 * h_l[max(l1, 0)]
    dist_levels = f"({fnum(d1)} {l1})"
    if l2 >= 1:
        d2 = d1 + 4.0 * h_l[l2]
        dist_levels += f" ({fnum(d2)} {l2})"

    # Background motion box: sweep the component box over roll 0..360 and
    # yaw/pitch +-max_tilt about the CoM, then add translation envelopes.
    corners = (
        np.array(
            [
                [x, y, z]
                for x in (cx0, cx1)
                for y in (-side, side)
                for z in (-side, side)
            ]
        )
        - com
    )
    tilt = math.radians(a.max_tilt_deg)
    swept = []
    for phi in np.radians(np.arange(0, 360, 15)):
        for psi in (-tilt, 0.0, tilt):
            for th in (-tilt, 0.0, tilt):
                Rm = rot_z(psi) @ rot_y(th) @ rot_x(phi)
                swept.append(corners @ Rm.T)
    swept = np.vstack(swept) + com
    env_y = a.envelope * L
    if a.vertical_envelope is not None:
        env_z = a.vertical_envelope * L
    else:
        env_z = float(np.clip(dz_unc, a.envelope * L, 3.0 * L))
    env = np.array([0.25 * L, env_y, env_z])
    b3_lo = swept.min(axis=0) - env - 2 * h_c
    b3_hi = swept.max(axis=0) + env + 2 * h_c
    b2_lo = b3_lo - np.array([0.5 * L, 0.5 * L, 0.5 * L])
    b2_hi = b3_hi + np.array([2.0 * L, 0.5 * L, 0.5 * L])
    b1_lo = b2_lo - np.array([0.5 * L, 0.5 * L, 0.5 * L])
    b1_hi = b2_hi + np.array([3.0 * L, 0.5 * L, 0.5 * L])
    dx0 = min(-3.0 * L, b1_lo[0] - 1.0 * L)
    dx1 = max(9.0 * L, b1_hi[0] + 1.5 * L)
    dy = max(3.0 * L, max(abs(b1_lo[1]), abs(b1_hi[1])) + 1.0 * L)
    dzh = max(3.0 * L, max(abs(b1_lo[2]), abs(b1_hi[2])) + 1.0 * L)
    nbx = int(math.ceil((dx1 - dx0) / h0))
    nby = int(math.ceil(2 * dy / h0))
    nbz = int(math.ceil(2 * dzh / h0))
    dom_lo = np.array([dx0, -0.5 * nby * h0, -0.5 * nbz * h0])
    dom_hi = dom_lo + np.array([nbx, nby, nbz]) * h0
    inner_lo, inner_hi = dom_lo + h0, dom_hi - h0
    boxes = []
    for blo, bhi in ((b1_lo, b1_hi), (b2_lo, b2_hi), (b3_lo, b3_hi)):
        boxes.append(
            (np.clip(blo, inner_lo, inner_hi), np.clip(bhi, inner_lo, inner_hi))
        )
    bg_point = dom_lo + np.array([0.37, 0.41, 0.43]) * h0

    # Rough cell-count estimate
    vols = [float(np.prod(bh - bl)) for bl, bh in boxes]
    v_dom = float(np.prod(dom_hi - dom_lo))
    n_bg = (
        (v_dom - vols[0]) / h0**3
        + (vols[0] - vols[1]) / (h0 / 2) ** 3
        + (vols[1] - vols[2]) / (h0 / 4) ** 3
        + vols[2] / (h0 / 8) ** 3
    ) * 1.15
    a_out = float(outer.area)
    n_comp = float(np.prod(cbox_hi - cbox_lo)) / h_c**3
    n_comp += 5.3 * a_out / h_l[smin] ** 2 * 1.3 + n_layers * a_out / h_l[smin] ** 2
    n_comp += (
        float(np.prod(np.maximum(wake_hi - wake_lo, 0))) / h_l[preset["wake"]] ** 3
    )
    n_total = n_bg + n_comp
    max_cells = int(max(2.0e7, 4.0 * n_total))

    # ------------------------------------------------------------------ #
    print("[7/8] Time stepping and inflow")
    # Smallest surface cell (layer cells are thin wall-normal, but the flow is
    # mostly tangential there, so they do not set the Courant number).
    h_min = h_l[smax]
    dt0 = 0.1 * h_min / U
    max_dt = min(T_spring / 40.0, 2.0e-3)
    k_in = 1.5 * (a.turbulence_intensity * U) ** 2
    omega_in = k_in / (nu * a.eddy_viscosity_ratio)
    if a.turbulence == "kOmegaSSTDDES" and a.max_co > 1.0:
        note("DDES selected: consider --max-co 1 or lower")
    n_steps_est = a.end_time / max(min(a.max_co * h_min / (1.3 * U), max_dt), 1e-9)

    t_tab = None
    if a.fluctuation_percent > 0.0:
        per = a.fluctuation_period
        dt_tab = min(per / 24.0, 0.02)
        t_tab = np.arange(0.0, a.end_time + per + dt_tab, dt_tab)
    elif a.ramp_time > 0.0:
        t_tab = np.linspace(0.0, a.ramp_time, 21)
    if t_tab is None:
        u_func = f"constant ({fnum(U)} 0 0)"
        u_internal = f"({fnum(U)} 0 0)"
        inflow_desc = "constant"
    else:
        ramp = (
            smoothstep(t_tab / a.ramp_time) if a.ramp_time > 0 else np.ones_like(t_tab)
        )
        fl = np.zeros((len(t_tab), 3))
        if a.fluctuation_percent > 0.0:
            rng = np.random.default_rng(a.seed)
            amp = a.fluctuation_percent / 100.0
            amps = (amp, a.fluctuation_lateral * amp, a.fluctuation_lateral * amp)
            for i in range(3):
                fr = rng.uniform(0.5, 2.0, 5) / a.fluctuation_period
                ph = rng.uniform(0.0, 2.0 * math.pi, 5)
                w = rng.uniform(0.5, 1.0, 5)
                sig = (
                    w[None, :]
                    * np.sin(2 * math.pi * fr[None, :] * t_tab[:, None] + ph[None, :])
                ).sum(axis=1)
                sig /= max(np.abs(sig).max(), 1e-12)
                fl[:, i] = amps[i] * sig
        uvec = U * ramp[:, None] * (np.array([1.0, 0.0, 0.0])[None, :] + fl)
        rows = "\n".join(
            f"            ({fnum(t, 7)} ({fvec(u, 7)}))" for t, u in zip(t_tab, uvec)
        )
        u_func = "table\n        (\n" + rows + "\n        )"
        u_internal = "(0 0 0)" if a.ramp_time > 0 else f"({fnum(U)} 0 0)"
        inflow_desc = f"table: ramp {a.ramp_time:g} s" + (
            f", fluctuations +-{a.fluctuation_percent:g}% "
            f"(period ~{a.fluctuation_period:g} s, lateral x"
            f"{a.fluctuation_lateral:g}, seed {a.seed})"
            if a.fluctuation_percent > 0
            else ""
        )

    # ------------------------------------------------------------------ #
    print(f"[8/8] Writing case to {out}")
    if out.exists():
        if not a.force:
            raise SystemExit(
                f"{out} exists (use --force to replace a case generated by this script)"
            )
        if not (out / "case_info.json").is_file() and any(out.iterdir()):
            raise SystemExit(
                f"refusing to delete {out}: not generated by "
                "prepare_case.py (no case_info.json)"
            )
        shutil.rmtree(out)
    shutil.copytree(TEMPLATE_DIR, out, ignore=shutil.ignore_patterns("__pycache__"))
    for script in ("Allrun", "Allclean"):
        (out / script).chmod(0o755)

    const = out / "background" / "constant"
    chosen = {
        "kOmegaSST": None,
        "kOmegaSSTDDES": "turbulenceProperties.DDES",
        "laminar": "turbulenceProperties.laminar",
    }[a.turbulence]
    if chosen:
        shutil.copyfile(const / chosen, const / "turbulenceProperties")
    for extra in ("turbulenceProperties.DDES", "turbulenceProperties.laminar"):
        (const / extra).unlink(missing_ok=True)

    div_u = {
        "kOmegaSST": "Gauss limitedLinearV 1",
        "kOmegaSSTDDES": "Gauss LUST grad(U)",
        "laminar": "Gauss limitedLinearV 1",
    }[a.turbulence]

    tokens = {
        # component mesh
        "C_XMIN": fnum(cbox_lo[0]),
        "C_YMIN": fnum(cbox_lo[1]),
        "C_ZMIN": fnum(cbox_lo[2]),
        "C_XMAX": fnum(cbox_hi[0]),
        "C_YMAX": fnum(cbox_hi[1]),
        "C_ZMAX": fnum(cbox_hi[2]),
        "C_NX": ncx,
        "C_NY": ncs,
        "C_NZ": ncs,
        "STL_FILE": "lure.stl",
        "ADD_LAYERS": "true" if n_layers > 0 else "false",
        "N_LAYERS": n_layers,
        "WAKE_MIN": fvec(wake_lo),
        "WAKE_MAX": fvec(wake_hi),
        "WAKE_LEVEL": preset["wake"],
        "FEATURE_LEVEL": smax,
        "SURF_MIN": smin,
        "SURF_MAX": smax,
        "DIST_LEVELS": dist_levels,
        "LOCATION_IN_MESH": fvec(loc_in_mesh),
        "MAX_GLOBAL_CELLS": max_cells,
        # background mesh
        "B_XMIN": fnum(dom_lo[0]),
        "B_YMIN": fnum(dom_lo[1]),
        "B_ZMIN": fnum(dom_lo[2]),
        "B_XMAX": fnum(dom_hi[0]),
        "B_YMAX": fnum(dom_hi[1]),
        "B_ZMAX": fnum(dom_hi[2]),
        "B_NX": nbx,
        "B_NY": nby,
        "B_NZ": nbz,
        "R1_MIN": fvec(boxes[0][0]),
        "R1_MAX": fvec(boxes[0][1]),
        "R2_MIN": fvec(boxes[1][0]),
        "R2_MAX": fvec(boxes[1][1]),
        "R3_MIN": fvec(boxes[2][0]),
        "R3_MAX": fvec(boxes[2][1]),
        "BG_LOCATION": fvec(bg_point),
        "BG_POINT": fvec(bg_point),
        # numerics
        "END_TIME": fnum(a.end_time),
        "DELTA_T": fnum(dt0, 4),
        "WRITE_INTERVAL": fnum(a.write_interval),
        "SURFACE_INTERVAL": fnum(a.surface_interval),
        "MAX_CO": fnum(a.max_co),
        "MAX_DELTA_T": fnum(max_dt, 4),
        "DDT_SCHEME": a.ddt,
        "DIV_U": div_u,
        "N_OUTER": max(1, a.n_outer),
        "NPROCS": max(1, a.nprocs),
        # physics
        "RHO": fnum(rho_w, 6),
        "NU": fnum(nu, 6),
        "COM": fvec(com),
        "MASS": fnum(M),
        "INERTIA": fvec(I_princ),
        "ORIENTATION": fvec(E),  # row-major: (xx xy xz yx ...) of Q, columns = axes
        "GRAVITY": f"0 0 {fnum(-gmag)}",
        "ACCEL_RELAX": fnum(a_relax, 3),
        "ACCEL_DAMP": fnum(a.accel_damp, 3),
        "ANCHOR": fvec(anchor),
        "ATTACH": fvec(tow),
        "K_LEADER": fnum(k_leader),
        "C_LEADER": fnum(c_leader),
        "LEADER_LENGTH": fnum(a.leader_m),
        "BUOY_ANCHOR": fvec(buoy_anchor, 12),
        "BUOY_ATTACH": fvec(cob, 12),
        "K_BUOY": fnum(k_buoy),
        "U_INTERNAL": u_internal,
        "INLET_U_FUNCTION": u_func,
        "K_IN": fnum(k_in),
        "OMEGA_IN": fnum(omega_in),
    }
    fill_tokens(out, tokens, keep_buoyancy=not a.no_gravity)
    write_stl(
        out / "lureMesh" / "constant" / "triSurface" / "lure.stl",
        outer,
        ascii_stl=a.ascii_stl,
    )

    info = {
        "generator": "tools/cfd/openfoam_lure/prepare_case.py",
        "created_utc": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "openfoam_release": OPENFOAM_RELEASE,
        "command": " ".join(
            [Path(sys.argv[0]).name] + (argv if argv is not None else sys.argv[1:])
        ),
        "inputs": {
            k: (v if not isinstance(v, Path) else str(v)) for k, v in vars(a).items()
        },
        "stl": {
            "path": a.stl,
            "triangles": len(raw.faces),
            "units": a.units,
            "scale_to_m": s,
            "rotation_case_from_stl": R.tolist(),
            "translation_m": t_vec.tolist(),
            "note": "case = rotation @ (scale * stl) + translation",
            "orientation": orient_info,
            "outer_shells": len(outer_parts),
            "sealed_cavities": len(cavities),
            "dropped_slivers": len(dropped),
        },
        "geometry": {
            "length_m": L,
            "width_m": 2 * half_y,
            "height_m": 2 * half_z,
            "bbox_min_m": lo.tolist(),
            "bbox_max_m": hi.tolist(),
            "frontal_area_m2": A_front,
            "wetted_area_m2": a_out,
            "displaced_volume_m3": vol_disp,
            "printed_volume_m3": vol_solid,
            "centre_of_buoyancy_m": cob.tolist(),
            "tail_point_m": outer.vertices[np.argmax(outer.vertices[:, 0])].tolist(),
        },
        "mass": {
            "model": mass_model,
            "density_kg_m3": rho_mat,
            "infill": a.infill,
            "wall_m": wall,
            "voxel_m": h_vox,
            "shell_volume_fraction": shell_frac,
            "printed_mass_kg": m_p,
            "ballast_kg": m_ball,
            "ballast_pos_m": None if r_ball is None else r_ball.tolist(),
            "mass_kg": M,
            "centre_of_mass_m": com.tolist(),
            "inertia_about_com_kg_m2": I.tolist(),
            "principal_moments_kg_m2": I_princ.tolist(),
            "orientation_Q0": E.tolist(),
            "solid_100pct_mass_kg": exact_m,
            "checks": check,
        },
        "hydrostatics": {
            "gravity_on": not a.no_gravity,
            "g_m_s2": G0,
            "buoyancy_N": B,
            "weight_N": W,
            "net_down_N": W - B,
            "cob_minus_com_m": (cob - com).tolist(),
            "roll_stiffness_N_m_per_rad": K_roll,
            "buoyancy_spring": {
                "anchor_m": buoy_anchor.tolist(),
                "attachment_m": cob.tolist(),
                "stiffness_N_m": k_buoy,
                "height_m": buoy_H,
            },
        },
        "flow": {
            "speed_mph": a.speed_mph,
            "U_m_s": U,
            "rho_kg_m3": rho_w,
            "nu_m2_s": nu,
            "Re_L": Re,
            "water": a.water,
            "temp_c": a.water_temp_c,
            "turbulence": a.turbulence,
            "k_in": k_in,
            "omega_in": omega_in,
            "inflow": inflow_desc,
            "ramp_time_s": a.ramp_time,
            "fluctuation_percent": a.fluctuation_percent,
        },
        "leader": {
            "rigging": a.rigging,
            "length_m": a.leader_m,
            "tow_point_m": tow.tolist(),
            "tow_point_source": tow_src,
            "anchor_m": anchor.tolist(),
            "elevation_deg": math.degrees(elev),
            "elevation_source": elev_src,
            "azimuth_deg": a.line_azimuth_deg,
            "stiffness_N_m": k_leader,
            "damping_N_s_m": c_leader,
            "axial_period_s": T_spring,
            "drag_estimate_N": D_est,
            "cd_estimate": a.cd_estimate,
            "vertical_uncertainty_m": dz_unc,
        },
        "sixdof": {
            "accelerationRelaxation": a_relax,
            "accelerationDamping": a.accel_damp,
            "added_mass_lateral_kg": m_added,
            "added_mass_ratio": added_ratio,
            "solver": "Newmark",
            "report": True,
        },
        "mesh": {
            "level": a.mesh_level,
            "component_base_cell_m": h_c,
            "background_base_cell_m": h0,
            "surface_levels": [smin, smax],
            "surface_cell_m": [h_l[smin], h_l[smax]],
            "layers": n_layers,
            "component_box_m": [cbox_lo.tolist(), cbox_hi.tolist()],
            "domain_m": [dom_lo.tolist(), dom_hi.tolist()],
            "refinement_boxes_m": [[b[0].tolist(), b[1].tolist()] for b in boxes],
            "motion_envelope_m": env.tolist(),
            "estimated_cells_background": int(n_bg),
            "estimated_cells_component": int(n_comp),
            "estimated_cells_total": int(n_total),
            "blockage_ratio": A_front
            / float((dom_hi[1] - dom_lo[1]) * (dom_hi[2] - dom_lo[2])),
        },
        "time": {
            "end_time_s": a.end_time,
            "initial_dt_s": dt0,
            "max_dt_s": max_dt,
            "max_co": a.max_co,
            "write_interval_s": a.write_interval,
            "surface_interval_s": a.surface_interval,
            "ddt": a.ddt,
            "estimated_time_steps": int(n_steps_est),
        },
        "notes": notes,
    }
    (out / "case_info.json").write_text(json.dumps(info, indent=2))

    readme = f"""# Generated lure case: {stl_path.name}

Generated by `prepare_case.py` on {info["created_utc"]} for {OPENFOAM_RELEASE}.
**OpenFOAM has not been run on this case by the generator.**

| quantity | value |
|---|---|
| tow speed | {a.speed_mph:g} mph = {U:.3f} m/s, Re_L = {Re:.3g} |
| lure length / width / height | {L * 1e3:.1f} / {2 * half_y * 1e3:.1f} / {2 * half_z * 1e3:.1f} mm |
| mass (printed + ballast) | {m_p * 1e3:.2f} + {m_ball * 1e3:.2f} = {M * 1e3:.2f} g |
| displaced volume, buoyancy | {vol_disp * 1e6:.2f} cm3, {B:.4f} N |
| net weight in water | {W - B:+.4f} N ({"sinks" if W > B else "floats"}){" - gravity OFF" if a.no_gravity else ""} |
| centre of mass (case coords) | ({fvec(com * 1e3, 5)}) mm |
| centre of buoyancy | ({fvec(cob * 1e3, 5)}) mm |
| principal inertia | ({fvec(I_princ, 4)}) kg m2 |
| tow point | ({fvec(tow * 1e3, 5)}) mm, {tow_src} |
| leader | {a.leader_m} m, elevation {math.degrees(elev):+.1f} deg, k {k_leader:.0f} N/m |
| mesh level | {a.mesh_level}: ~{n_total / 1e6:.2f} M cells (rough estimate) |
| inflow | {inflow_desc} |
| turbulence | {a.turbulence} |

Run (OpenFOAM v2412 environment sourced):

```bash
./Allrun -np 8            # or ./Allrun for serial, ./Allrun -mesh-only to inspect
python3 <repo>/tools/cfd/openfoam_lure/postprocess.py .
```

Re-generate this case with:

```bash
{info["command"]}
```
"""
    if notes:
        readme += "\nNotes:\n\n" + "\n".join(f"- {n_}" for n_ in notes) + "\n"
    (out / "README_CASE.md").write_text(readme)

    issues = check_case_dir(out)
    if issues:
        for k, v in issues.items():
            print(f"  CHECK FAILED {k}: {v}")
        raise SystemExit("generated case failed the dictionary checks")

    print("\nSummary")
    print(f"  case                {out}")
    print(f"  speed               {a.speed_mph:g} mph ({U:.3f} m/s), Re_L {Re:.3g}")
    print(
        f"  mass                {M * 1e3:.2f} g, net {'down' if W > B else 'up'} "
        f"{abs(W - B):.4f} N"
    )
    print(
        f"  mesh                {a.mesh_level}: ~{n_bg / 1e6:.2f} M background + "
        f"~{n_comp / 1e6:.2f} M component cells (rough)"
    )
    print(
        f"  domain              {fvec((dom_hi - dom_lo), 4)} m, base cell {h0 * 1e3:.1f} mm, "
        f"finest bg {h_c * 1e3:.2f} mm, surface {h_l[smin] * 1e3:.2f}-{h_l[smax] * 1e3:.2f} mm"
    )
    print(
        f"  time                end {a.end_time:g} s, dt0 {dt0:.2e} s, max dt "
        f"{max_dt:.2e} s, ~{n_steps_est:.0f} steps at maxCo {a.max_co:g}"
    )
    print("  checks              all dictionaries balanced, no leftover tokens")
    print(
        "  next                cd <case> && ./Allrun -np <N>   (needs OpenFOAM v2412)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
