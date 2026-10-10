#!/usr/bin/env python3
"""
Static checks of a generated case (or the template) without OpenFOAM:

  python tests/check_case.py <case_dir> [--template]

* every OpenFOAM dictionary has balanced {} and () (comments/strings ignored)
* no @@TOKEN@@ placeholders are left (skipped with --template)
* required files exist
* Allrun / Allclean are executable

Uses the same checker as prepare_case.py. Exit code 0 = OK.
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent

REQUIRED = [
    "Allrun",
    "Allclean",
    "lureMesh/system/controlDict",
    "lureMesh/system/blockMeshDict",
    "lureMesh/system/snappyHexMeshDict",
    "lureMesh/system/surfaceFeatureExtractDict",
    "lureMesh/system/createPatchDict",
    "lureMesh/system/fvSchemes",
    "lureMesh/system/fvSolution",
    "background/system/controlDict",
    "background/system/blockMeshDict",
    "background/system/snappyHexMeshDict",
    "background/system/topoSetDict",
    "background/system/setFieldsDict",
    "background/system/fvSchemes",
    "background/system/fvSolution",
    "background/system/decomposeParDict",
    "background/constant/dynamicMeshDict",
    "background/constant/transportProperties",
    "background/constant/turbulenceProperties",
    "background/0.orig/U",
    "background/0.orig/p",
    "background/0.orig/k",
    "background/0.orig/omega",
    "background/0.orig/nut",
    "background/0.orig/pointDisplacement",
    "background/0.orig/zoneID",
]


def load_prepare_case():
    spec = importlib.util.spec_from_file_location(
        "prepare_case", HERE.parent / "prepare_case.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("case")
    ap.add_argument(
        "--template",
        action="store_true",
        help="checking the template: placeholders are expected",
    )
    a = ap.parse_args()
    case = Path(a.case).resolve()
    pc = load_prepare_case()
    problems = 0
    for rel in REQUIRED:
        if not (case / rel).is_file():
            print(f"[FAIL] missing {rel}")
            problems += 1
    for script in ("Allrun", "Allclean"):
        p = case / script
        if p.is_file() and not os.access(p, os.X_OK):
            print(f"[FAIL] {script} is not executable")
            problems += 1
    n_files = 0
    for p in sorted(case.rglob("*")):
        if (
            not p.is_file()
            or not pc.is_text_dict(p)
            or p.name in ("Allrun", "Allclean")
        ):
            continue
        if p.suffix in (".md", ".json", ".py", ".sh"):
            continue
        n_files += 1
        txt = p.read_text(errors="replace")
        issues = pc.check_foam_text(txt)
        if a.template:
            issues = [i for i in issues if not i.startswith("leftover placeholder")]
        for i in issues:
            print(f"[FAIL] {p.relative_to(case)}: {i}")
            problems += 1
    if not a.template:
        for rel, iss in pc.check_case_dir(case).items():
            print(f"[FAIL] {rel}: {iss}")
            problems += 1
    print(
        f"checked {n_files} dictionaries in {case}: "
        + ("OK" if problems == 0 else f"{problems} problem(s)")
    )
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
