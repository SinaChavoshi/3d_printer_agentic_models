#!/usr/bin/env python3
"""
Fabricate a small synthetic "OpenFOAM run" so postprocess.py can be tested
without OpenFOAM:

  <out>/case_info.json                                  (minimal subset)
  <out>/background/log.overPimpleDyMFoam                ('report on' format)
  <out>/background/postProcessing/lureForces/0/force.dat
  <out>/background/postProcessing/sixDoF/0/sixDoFRigidBodyState.dat
  <out>/background/<t>/uniform/sixDoFRigidBodyMotionState   (every 0.05 s)
  <out>/background/postProcessing/lureSurface/<t>/lure.vtp  (dummy files)
  <out>/expected.json                                   (ground truth)

Prescribed motion (relative to a slightly tilted initial principal frame Q0):
  spin 2.5 rev/s about the lure axis, yaw 8 deg @ 3.2 Hz, pitch 3 deg @ 1.3 Hz,
  sway 6 mm @ 3.2 Hz, heave 2 mm @ 1.3 Hz, surge 1 mm @ 0.3 Hz;
  drag 0.30 N + 0.02 N @ 6.4 Hz, side force 0.05 N @ 3.2 Hz.
Variable time steps (0.8-1.2 ms) exercise the resampling.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

SPIN_REV_S = 2.5
F_YAW, A_YAW = 3.2, 8.0  # Hz, deg
F_PITCH, A_PITCH = 1.3, 3.0  # Hz, deg
A_SWAY, A_HEAVE, A_SURGE = 6e-3, 2e-3, 1e-3  # m
T_END = 4.0


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def r_rel(t):
    phi = 2 * math.pi * SPIN_REV_S * t
    psi = math.radians(A_YAW) * math.sin(2 * math.pi * F_YAW * t)
    th = math.radians(A_PITCH) * math.sin(2 * math.pi * F_PITCH * t + 0.4)
    return rz(psi) @ ry(th) @ rx(phi)


def com_disp(t):
    return np.array(
        [
            A_SURGE * math.sin(2 * math.pi * 0.3 * t),
            A_SWAY * math.sin(2 * math.pi * F_YAW * t + 0.7),
            A_HEAVE * math.sin(2 * math.pi * F_PITCH * t),
        ]
    )


def com_vel(t):
    return np.array(
        [
            A_SURGE * 2 * math.pi * 0.3 * math.cos(2 * math.pi * 0.3 * t),
            A_SWAY * 2 * math.pi * F_YAW * math.cos(2 * math.pi * F_YAW * t + 0.7),
            A_HEAVE * 2 * math.pi * F_PITCH * math.cos(2 * math.pi * F_PITCH * t),
        ]
    )


def omega_global(t, d=1e-6):
    R1, R0 = r_rel(t + d), r_rel(t - d)
    Om = ((R1 - R0) / (2 * d)) @ r_rel(t).T
    Om = 0.5 * (Om - Om.T)
    return np.array([Om[2, 1], Om[0, 2], Om[1, 0]])


def fv(v):
    """OpenFOAM-style vector/tensor output (6 significant digits)."""
    return "(" + " ".join(f"{x:.6g}" for x in np.ravel(v)) + ")"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("out", help="output directory (created)")
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args(argv)
    out = Path(a.out)
    bg = out / "background"
    (bg / "postProcessing" / "lureForces" / "0").mkdir(parents=True, exist_ok=True)
    (bg / "postProcessing" / "sixDoF" / "0").mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(a.seed)
    Q0 = ry(math.radians(2.0)) @ rz(math.radians(0.5))
    com0 = np.array([0.046, 0.0, 0.0007])
    tow0 = np.array([0.014, 0.0, 0.0])
    tail0 = np.array([0.1178, 0.0, 0.0])
    elev0 = math.radians(-20.0)
    Lrest = 1.2 - 0.0009
    anchor = tow0 + 1.2 * np.array([-math.cos(elev0), 0.0, math.sin(elev0)])
    k = 333.333
    Idiag = np.array([1.43e-6, 1.21e-5, 1.21e-5])
    rho, U, A = 999.1, 1.1176, 5.322e-4
    cob0 = np.array([0.0460, 0.0, 0.00048])

    t = [0.0]
    while t[-1] < T_END:
        t.append(t[-1] + rng.uniform(0.8e-3, 1.2e-3))
    t = np.array(t[1:])

    log = [
        "/*---------------------------------------------------------------------------*\\",
        "  synthetic overPimpleDyMFoam log (postprocess.py test)",
        "\\*---------------------------------------------------------------------------*/",
        "Starting time loop",
        "",
    ]
    dat = [
        "# Motion State",
        "# Angle Units : degrees",
        "# ",
        "# Time\tcentreOfRotation\tcentreOfMass\trotation\tvelocity\tomega",
    ]
    frc = [
        "# Force",
        "# CofR : (0.046 0 0.0007)",
        "# ",
        "# Time\ttotal_x total_y total_z\tpressure_x pressure_y pressure_z\t"
        "viscous_x viscous_y viscous_z",
    ]
    elev, tension, roll_proj = [], [], []
    next_write = 0.05
    for i, ti in enumerate(t):
        Rr = r_rel(ti)
        Q = Rr @ Q0
        com = com0 + com_disp(ti)
        v = com_vel(ti)
        w = omega_global(ti)
        att = com + Rr @ (tow0 - com0)
        r = att - anchor
        L = np.linalg.norm(r)
        F = -k * (L - Lrest) * r / L
        line = anchor - att
        elev.append(math.degrees(math.atan2(line[2], math.hypot(line[0], line[1]))))
        tension.append(k * (L - Lrest))  # signed (< 0 = compression)
        roll_proj.append(w @ (Rr[:, 0]))
        cob = com + Rr @ (cob0 - com0)
        rb = cob - (cob0 + np.array([0, 0, 1e4]))
        Fb = np.array([0.0, 0.0, 0.3091])
        log += [
            "Courant Number mean: 0.01 max: 1.9",
            f"deltaT = {t[i] - (t[i - 1] if i else 0.0):.6g}",
            f"Time = {ti:.8g}",
            "",
            f"Restraint leader:  attachmentPt - anchor {fv(r)} spring length "
            f"{L:.9g} force {fv(F)}",
            f"Restraint buoyancy:  attachmentPt - anchor {fv(rb)} spring length "
            f"{np.linalg.norm(rb):.9g} force {fv(Fb)}",
            "6-DoF rigid body motion",
            f"    Centre of rotation: {fv(com)}",
            f"    Centre of mass: {fv(com)}",
            f"    Orientation: {fv(Q)}",
            f"    Linear velocity: {fv(v)}",
            f"    Angular velocity: {fv(w)}",
            "Execution time for mesh.update() = 0.01 s",
            "PIMPLE: iteration 1",
            f"ExecutionTime = {i * 0.1:.2f} s  ClockTime = {int(i * 0.1)} s",
            "",
        ]
        # sixDoFRigidBodyState.dat: Euler XYZ (R = Rx(a) Ry(b) Rz(c)) in degrees
        b = math.asin(max(-1.0, min(1.0, Q[0, 2])))
        aa = math.atan2(-Q[1, 2], Q[2, 2])
        c = math.atan2(-Q[0, 1], Q[0, 0])
        dat.append(
            f"{ti:.8g}\t{fv(com)}\t{fv(com)}\t"
            f"{fv(np.degrees([aa, b, c]))}\t{fv(v)}\t{fv(np.degrees(w))}"
        )
        Fx = 0.30 + 0.02 * math.sin(2 * math.pi * 6.4 * ti)
        Fy = 0.05 * math.sin(2 * math.pi * F_YAW * ti + 1.0)
        Fz = -0.01 + 0.005 * math.sin(2 * math.pi * F_PITCH * ti)
        tot = np.array([Fx, Fy, Fz])
        frc.append(
            f"{ti:.8g}\t"
            + "\t".join(f"{x:.8g}" for x in np.concatenate([tot, 0.9 * tot, 0.1 * tot]))
        )
        if ti >= next_write - 1e-12:
            tdir = bg / f"{next_write:.6g}" / "uniform"
            tdir.mkdir(parents=True, exist_ok=True)
            pi_body = Idiag * (Q.T @ w)
            (tdir / "sixDoFRigidBodyMotionState").write_text(
                "FoamFile\n{\n    version 2.0;\n    format ascii;\n    class dictionary;\n"
                "    object sixDoFRigidBodyMotionState;\n}\n"
                f"centreOfRotation {fv(com)};\norientation {fv(Q)};\nvelocity {fv(v)};\n"
                f"acceleration (0 0 0);\nangularMomentum {fv(pi_body)};\ntorque (0 0 0);\n"
            )
            if next_write < 0.2:  # a few dummy surface files for the .series test
                sdir = bg / "postProcessing" / "lureSurface" / f"{next_write:.6g}"
                sdir.mkdir(parents=True, exist_ok=True)
                (sdir / "lure.vtp").write_text("<VTKFile/>\n")
            next_write += 0.05
    log.append("End")
    (bg / "log.overPimpleDyMFoam").write_text("\n".join(log) + "\n")
    (bg / "postProcessing" / "sixDoF" / "0" / "sixDoFRigidBodyState.dat").write_text(
        "\n".join(dat) + "\n"
    )
    (bg / "postProcessing" / "lureForces" / "0" / "force.dat").write_text(
        "\n".join(frc) + "\n"
    )

    info = {
        "generator": "tests/make_synthetic_run.py",
        "mass": {
            "orientation_Q0": Q0.tolist(),
            "centre_of_mass_m": com0.tolist(),
            "principal_moments_kg_m2": Idiag.tolist(),
        },
        "leader": {
            "tow_point_m": tow0.tolist(),
            "anchor_m": anchor.tolist(),
            "length_m": Lrest,
            "stiffness_N_m": k,
            "elevation_deg": math.degrees(elev0),
        },
        "geometry": {"tail_point_m": tail0.tolist(), "frontal_area_m2": A},
        "flow": {"U_m_s": U, "rho_kg_m3": rho},
        "mesh": {"motion_envelope_m": [0.03, 0.12, 0.12]},
    }
    (out / "case_info.json").write_text(json.dumps(info, indent=2))

    t0 = t[0] + min(max(0.25 * t[-1], 0.5), 0.5 * t[-1])
    win = t >= t0
    exp = {
        "roll_rate_mean_rpm": float(
            np.mean(np.array(roll_proj)[win]) * 60 / (2 * math.pi)
        ),
        "roll_rate_design_rpm": SPIN_REV_S * 60.0,
        "rotations_in_window": float(
            np.trapezoid(np.array(roll_proj)[win], t[win]) / (2 * math.pi)
        ),
        "yaw_freq_hz": F_YAW,
        "sway_freq_hz": F_YAW,
        "heave_freq_hz": F_PITCH,
        "pitch_freq_hz": F_PITCH,
        "side_force_freq_hz": F_YAW,
        "yaw_p2p_deg": 2 * A_YAW,
        "sway_p2p_mm": 2 * A_SWAY * 1e3,
        "line_elevation_mean_deg": float(np.mean(np.array(elev)[win])),
        "line_tension_mean_N": float(np.mean(np.array(tension)[win])),
        "line_slack_fraction": float(np.mean(np.array(tension)[win] <= 0.0)),
        "drag_mean_N": 0.30,
        "Cd_frontal": 0.30 / (0.5 * rho * U * U * A),
        "analysis_start_s": float(t[win][0]),
    }
    (out / "expected.json").write_text(json.dumps(exp, indent=2))
    print(f"synthetic run with {len(t)} steps written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
