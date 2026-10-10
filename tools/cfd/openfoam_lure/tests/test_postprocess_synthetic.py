#!/usr/bin/env python3
"""
Regression test for postprocess.py on a fabricated run (no OpenFOAM needed).

  python tests/test_postprocess_synthetic.py [workdir]

Generates the synthetic run (tests/make_synthetic_run.py), runs postprocess.py
with each state source (log, sixDoFRigidBodyState.dat, uniform/ states) and
compares the extracted metrics with the prescribed motion. Exit code 0 = pass.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# (metric, tolerance, kind) - kind 'abs' or 'rel'
CHECKS = {
    "log": [
        ("roll_rate_mean_rpm", 0.5, "abs"),
        ("rotations_in_window", 0.02, "abs"),
        ("yaw_freq_hz", 0.05, "abs"),
        ("sway_freq_hz", 0.05, "abs"),
        ("heave_freq_hz", 0.05, "abs"),
        ("pitch_freq_hz", 0.05, "abs"),
        ("side_force_freq_hz", 0.05, "abs"),
        ("yaw_p2p_deg", 0.3, "abs"),
        ("sway_p2p_mm", 0.1, "abs"),
        ("line_elevation_mean_deg", 0.02, "abs"),
        ("line_tension_mean_N", 0.01, "rel"),
        ("line_slack_fraction", 0.01, "abs"),
        ("drag_mean_N", 0.002, "abs"),
        ("Cd_frontal", 0.01, "rel"),
    ],
    "dat": [
        ("roll_rate_mean_rpm", 0.5, "abs"),
        ("yaw_freq_hz", 0.05, "abs"),
        ("sway_freq_hz", 0.05, "abs"),
        ("yaw_p2p_deg", 0.3, "abs"),
        ("line_elevation_mean_deg", 0.02, "abs"),
    ],
    "uniform": [  # write-time sampling only (20 Hz): coarser tolerances
        ("roll_rate_mean_rpm", 3.0, "abs"),
        ("yaw_freq_hz", 0.15, "abs"),
        ("sway_freq_hz", 0.15, "abs"),
        ("yaw_p2p_deg", 1.5, "abs"),
    ],
}


def run(work: Path) -> int:
    """Generates the synthetic run in `work`, post-processes it, returns the failure count."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg")
    py = sys.executable
    subprocess.run(
        [py, str(HERE / "make_synthetic_run.py"), str(work)], check=True, env=env
    )
    exp = json.loads((work / "expected.json").read_text())
    failures = 0
    for src, checks in CHECKS.items():
        out = work / f"postprocess_{src}"
        cmd = [
            py,
            str(ROOT / "postprocess.py"),
            str(work),
            "--source",
            src,
            "--out",
            str(out),
        ]
        if src != "log":
            cmd.append("--no-plots")
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout, res.stderr)
            print(f"[FAIL] postprocess.py --source {src} exited {res.returncode}")
            failures += 1
            continue
        got = json.loads((out / "summary.json").read_text())["metrics"]
        print(
            f"--- source = {src}: {json.loads((out / 'summary.json').read_text())['meta']['state_source']}"
        )
        for key, tol, kind in checks:
            ref = exp[key]
            val = got.get(key, {}).get("value")
            err = (
                None
                if val is None
                else (abs(val - ref) if kind == "abs" else abs(val - ref) / abs(ref))
            )
            ok = err is not None and err <= tol
            failures += 0 if ok else 1
            print(
                f"  [{'PASS' if ok else 'FAIL'}] {key:28s} got {val!s:>22s}  "
                f"expected {ref:.6g}  ({kind} tol {tol})"
            )
        if src == "log":
            pngs = sorted(p.name for p in out.glob("*.png"))
            series = sorted(p.name for p in out.glob("*.vtp.series"))
            need = {
                "roll.png",
                "attitude.png",
                "position.png",
                "trajectory.png",
                "spectra.png",
                "line_forces.png",
            }
            ok = need.issubset(pngs) and series == ["lureSurface_lure.vtp.series"]
            failures += 0 if ok else 1
            print(f"  [{'PASS' if ok else 'FAIL'}] outputs: {pngs + series}")
    print("\nRESULT:", "PASS" if failures == 0 else f"FAIL ({failures} check(s))")
    return failures


def test_postprocess_synthetic(tmp_path):
    """pytest entry point: all metrics recovered from the fabricated run."""
    assert run(tmp_path / "synthetic") == 0


def main():
    work = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".validation" / "synthetic"
    )
    return 0 if run(work) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
