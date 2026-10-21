"""Exports print-ready binary STL files for the OpenSCAD models.

Every model gets `<model>.stl` next to its `.scad`. Models whose default render
is an assembled/preview view are exported as one STL per printable part (see
PARTS below), using OpenSCAD -D overrides.

Usage:
  python tools/render_scad/export_stl.py                                  # all models
  python tools/render_scad/export_stl.py generated_models/openscad/leitner_box
  python tools/render_scad/export_stl.py --openscad /path/to/openscad
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "generated_models" / "openscad"

# Models that need specific settings for printing. Values are OpenSCAD -D
# overrides (string values must include their quotes).
PARTS: dict[str, list[tuple[str, dict[str, str]]]] = {
    # Default view stacks the lid on the rim; print the three parts separately.
    "leitner_box/leitner_box.scad": [
        ("leitner_box_rim.stl", {"print_mode": "2"}),
        ("leitner_box_lid.stl", {"print_mode": "1"}),
        ("leitner_box_day_marker_peg.stl", {"print_mode": "3"}),
    ],
    # Default view is an exploded assembly; the box needs 2 latches.
    "rugged_enclosure/rugged_enclosure.scad": [
        ("rugged_enclosure_body.stl", {"part_to_show": '"body"'}),
        ("rugged_enclosure_lid.stl", {"part_to_show": '"lid"'}),
        ("rugged_enclosure_latch.stl", {"part_to_show": '"latch"'}),
    ],
    # The 340 mm bar is split into two dovetailed halves that fit normal beds.
    "window_exhaust_adapter/window_exhaust_adapter.scad": [
        ("window_exhaust_adapter_left_male.stl", {"print_selection": "1"}),
        ("window_exhaust_adapter_right_female.stl", {"print_selection": "2"}),
    ],
    # Four-colour kit: one plate per filament colour.
    "race_car_kit/race_car_kit.scad": [
        ("race_car_kit_body.stl", {"print_part": "1"}),
        ("race_car_kit_black.stl", {"print_part": "2"}),
        ("race_car_kit_white.stl", {"print_part": "3"}),
        ("race_car_kit_orange.stl", {"print_part": "4"}),
    ],
    # The model's own comment recommends 80-100 slices before exporting an STL.
    "salmon_fishing_spoon/salmon_fishing_spoon.scad": [
        ("salmon_fishing_spoon.stl", {"render_steps": "100"}),
    ],
}


def exports_for(scad: Path) -> list[tuple[str, dict[str, str]]]:
    rel = scad.resolve().relative_to(MODELS).as_posix()
    return PARTS.get(rel, [(scad.with_suffix(".stl").name, {})])


def export(
    scad: Path, out_name: str, overrides: dict[str, str], openscad: str
) -> tuple[Path, list[str]]:
    out = scad.parent / out_name
    cmd = [openscad, "--export-format", "binstl", "-o", str(out)]
    for name, value in overrides.items():
        cmd += ["-D", f"{name}={value}"]
    cmd.append(str(scad))
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not out.exists() or out.stat().st_size <= 84:
        raise RuntimeError(f"{scad.name} -> {out_name} failed:\n{res.stderr[-2000:]}")
    warnings = [
        line.strip()
        for line in res.stderr.splitlines()
        if "WARNING" in line or "ERROR" in line
    ]
    return out, warnings


def describe(path: Path) -> str:
    size = f"{path.stat().st_size / 1024:.0f} KB"
    try:
        import trimesh
    except ImportError:
        return size
    mesh = trimesh.load_mesh(path)
    extents = " x ".join(f"{e:.1f}" for e in mesh.extents)
    return f"{size}, {len(mesh.faces)} triangles, {extents} mm, watertight={mesh.is_watertight}"


def find_models(targets: list[str]) -> list[Path]:
    if not targets:
        return sorted(MODELS.glob("*/*.scad"))
    scads: list[Path] = []
    for target in targets:
        path = Path(target)
        scads += sorted(path.glob("*.scad")) if path.is_dir() else [path]
    return scads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "targets", nargs="*", help="Model folders or .scad files (default: all models)"
    )
    parser.add_argument(
        "--openscad",
        default=shutil.which("openscad") or "openscad",
        help="OpenSCAD executable",
    )
    args = parser.parse_args(argv)

    failures = 0
    for scad in find_models(args.targets):
        for out_name, overrides in exports_for(scad):
            try:
                out, warnings = export(scad, out_name, overrides, args.openscad)
            except (RuntimeError, OSError) as err:
                failures += 1
                print(f"FAIL {err}", file=sys.stderr)
                continue
            print(f"OK   {out.relative_to(REPO)}  ({describe(out)})")
            for warning in warnings:
                print(f"     {warning}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
