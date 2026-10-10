# LureHydro 3D: geometry-driven trolling-lure simulator

`index.html` is a single, self-contained page (no CDN, no external scripts; it
works offline and through htmlpreview.github.io). Load a lure STL exported from
OpenSCAD and watch it being trolled behind a boat. **Nothing about the motion is
scripted**: roll, wobble, sway, pitch and depth all come out of forces computed
from the lure's own 3D surface, its mass distribution and the tow line.

> [!IMPORTANT]
> This is a **reduced-order model, not CFD**. It is meant for comparing designs
> and seeing *trends* (does a face angle make it roll, which way does ballast
> push it, roughly how fast does it spin) in real time. For high-fidelity flow
> fields and coefficients use the OpenFOAM pipeline in `tools/cfd/openfoam_lure/`.

## Quick start

1. Open `index.html` in a browser (desktop Chrome/Firefox/Safari/Edge).
2. Click **Load demo** or drag an `.stl` onto the drop zone or the viewport.
   The demos are procedural cut-plugs with a concave, flat or skewed 45° face,
   plus a symmetric spheroid control. The concave one rolls; the flat one and
   the spheroid do not.
3. Check **STL units** (OpenSCAD exports millimetres, the default), **Nose points
   to** (which STL axis is the front) and **Back (up) is**. The four lures in
   `generated_models/openscad/` are recognised by file name and get a preset
   (axes, line-through hole openings, hook mass and drag).
4. Choose the rig: **Tied to eye** (default eye = front-most point on the
   body centreline) or **Line-through** (entry and exit openings). Use
   **📍 Pick** to click a point on the lure, or type `x, y, z` in STL units.
5. Set print settings (material, infill, wall), ballast, hook mass, buoyancy
   mode, trolling speed (mph) and fluctuations. Watch the telemetry panel.
6. Use **Playback ¼ slow-mo** and **Camera: From behind** to see the roll
   clearly; **Pressure map** colours the surface by the same pressure law the
   solver uses; **Force vectors** shows line tension, hydrodynamic resultant,
   buoyancy, weight and the vortex-shedding force.

## Code layout

| Part | Where | Notes |
|---|---|---|
| Physics engine | `<script id="lure-physics">` in `index.html` | No DOM access; defines `globalThis.LurePhysics` (STL parsing, mesh processing, mass properties, hydrodynamics, integrator, telemetry, demo geometry). |
| UI / renderer | `<script id="lure-ui">` | Canvas 2D, devicePixelRatio-aware, painter's algorithm with back-face and near-plane culling. |
| Headless check | `physics_check.mjs` | Extracts the physics block, runs it in `node:vm`, loads STLs and prints telemetry and pass/fail checks. |

## What the model does

### Frames and units

SI units everywhere internally. The world frame moves with the *mean* boat
velocity (a Galilean frame): `+x` = direction of travel, `+y` = up, `+z` =
starboard; the water flows past at `-U`. The body frame is the STL's own axes
scaled to metres (no normalisation of physical size: the camera auto-fits
instead). Orientation is a unit quaternion.

### Mesh pipeline (on load)

1. **Parse**: binary if `84 + 50·triCount === byteLength`; otherwise ASCII if the
   file starts with `solid` (lines split on `/\r?\n/`, tokens on `/\s+/`).
   Truncated binaries and files that are neither are rejected with a clear
   message. The file input is reset so the same file can be reloaded, and
   `FileReader.onerror` is handled.
2. **Weld** vertices; flip winding if the signed volume is negative.
3. **Mass integrals** by signed tetrahedra on the *full-resolution* mesh: volume,
   centre of volume, second moments (sealed internal voids such as the
   cut-plug rattle chamber are subtracted automatically).
4. **Hydrodynamic elements** (the decimated copy used by the force loop, target
   3000 by default, 1500 to 6000 selectable): the original triangles are grouped
   by grid cell (centred on the centre of volume) and a 6-way normal bin. Each
   element keeps the exact area, the area-weighted centroid and the summed area
   vector. Total area and closure (ΣAn = 0) are preserved exactly, mirror
   symmetry is preserved, and thin parts such as spoon blades do not collapse.
5. **Exposure**: 5 rays per element (normal plus four tilted 35°) are cast
   against a BVH of the full mesh. Elements whose rays all hit the body (walls
   of sealed voids, through-holes, deep sockets) carry no flow load; partial
   hits scale the element area.
6. **Render mesh**: vertex clustering (also centred and normal-binned) to about 9k
   triangles. Original, physics and render counts are shown in the UI.

### Mass properties

The printed part is modelled as a skin of wall thickness `t` over the whole
surface (outer skin plus void and hole walls) and infill fraction `f` in the
rest: density field `ρ·[f·Solid + (1−f)·Skin]`, with skin volume `A·t` capped
at `V`. Ballast (g, at a picked or typed body point; default the centre of
volume) and hook/hardware (g, at the tail: rear centreline point for eye rigs,
exit opening for line-through) are point masses. The UI shows volume, mass,
net buoyancy (floats/sinks), CoM, CoB−CoM and the added mass.

*Buoyancy modes*: **As printed** (computed); **Neutral** scales every mass
uniformly so `m = ρ_w·V` (CoM unchanged, so the net vertical force is exactly
zero); **Target net buoyancy** does the same for a chosen net value in grams.
**Infill floods** adds the water that would fill an unsealed print's infill to
the moving mass.

### Hydrodynamic loads (every physics substep)

For each element with centroid `r` (relative to the CoM), unit normal `n`,
projected area `A_p` and wetted area `A_w`:

* Local relative water velocity `v = u_water − (v_body + ω × r)` (turbulence
  included).
* **Windward pressure** (`v·n < 0`): `F = −½ ρ C_p A_p (v·n)² n` with
  **`C_p = 1`**. This is modified-Newtonian theory with the incompressible
  stagnation value `C_p,max = 1`. It gives a sphere `C_D = 0.5` (measured
  ≈ 0.47 at Re ~ 1e5) and a flat plate `C_D = 1` from the front face alone.
* **Lee-side suction** (`v·n > 0`): `F = +½ ρ C_s A_p (v·n)² n` with
  **`C_s = 0.3`**, a mild stand-in for separated-wake base pressure
  (`C_p,base ≈ −0.3…−0.5` behind bluff bodies). Weighting by `(v·n)²` means
  only strongly inclined lee faces feel it. A flat plate normal to the flow
  then gets `C_D ≈ 1.3`.
* **Skin friction**: `F = ½ ρ C_f A_w |v_t| v_t` with the turbulent flat-plate
  law **`C_f = 0.074 Re^−0.2`**, where `Re = U·L/ν` uses the body length along
  the flow (Re ~ 0.8–1.2·10⁵ for these lures at 2.5 mph, giving C_f ≈ 0.0075).
  Printed layer lines and sharp edges are assumed to trip the boundary layer.
* Forces are summed and torques taken about the CoM. **This is what turns
  geometry into motion**: an angled cut face, a cupped spoon or a bent
  "banana" produces net side force and moments that depend on the
  instantaneous attitude.
* **Trailing hardware** (hook, skirt): point drag `½ ρ (C_dA) |v| v` at the
  tail point (default `C_dA = 30 mm²`; presets use 15–200 mm²).
* **Leader drag**: half of the straight leader's cross-flow drag
  (`d = 0.55 mm`, `C_d = 1.2`) acts at the attachment point.

**Added mass** (on by default): the lure is replaced by the ellipsoid with the
same volume second moments (semi-axes `a_i = √(5λ_i)`). Lamb's coefficients
`α_i` give translational added mass `α_i/(2−α_i)·ρV` along each principal axis
and the classical rotational added inertia. They are added to the rigid-body
mass/inertia tensors (Munk moment and fluid-acceleration terms are omitted). A
5" cut-plug gets ~25 g of lateral added mass on top of ~20 g of plastic, so
it is not unrealistically twitchy.

**Vortex shedding** (empirical): two van der Pol wake oscillators (Facchinetti et
al. 2004, `ε = 0.3`, `A = 12`) across the flow, at `f = St·U/D` with
**`St = 0.2`** and `D` the cross-flow thickness of the equivalent ellipsoid. The
lift is `½ ρ U² A_ref (C_L0/2) q` with **`C_L0 = 0.25`** (slider, 0 turns it
off). It acts on the body's long axis at the station of the lee-side area
centroid, so it yaws and sways the lure but never adds artificial roll.
Coupling to the lure's lateral acceleration allows lock-in. Frequencies above
`0.5/dt` are capped.

**Buoyancy** `ρ_w g V` acts at the centre of volume; **weight** `m g` acts at the
CoM.

### Tow line and rigging

* Leader of length `L` (default 1.2 m): tension-only spring-damper with
  `k = EA/L`, `EA = 600 N` (≈ 25 lb nylon mono) and damping ratio 0.3.
* **Tied to eye**: line attached at the chosen point; the body is free to
  rotate about it (swivel assumed: no line-twist torque).
* **Line-through**: for a frictionless line through a hole with a bead/hook
  knot at the exit, the line's net effect is the tension applied at the
  **entry** opening with the hook load at the **exit**. So it is modelled as a
  ball joint at the entry with the hardware at the exit, and the body is free
  to spin about the line, as on a real line-through cut-plug or spoon. Telemetry
  measures roll about the entry–exit axis in this mode.
* The tow point moves at trolling speed with optional **surge** (± % of speed
  at f), **heave** (± cm at f) and **flasher/dodger sway** (± cm at f).

### Flow

Uniform current `U` (default **2.5 mph = 1.118 m/s**, slider in mph with m/s
readout) plus Ornstein–Uhlenbeck turbulence per axis (intensity × U standard
deviation, correlation time τ), exactly discretised and **seedable**. Salt water
1025 kg/m³ (ν = 1.35·10⁻⁶ m²/s, ~10 °C) or fresh 1000 kg/m³ (ν = 1.14·10⁻⁶).

### Integrator

Fixed physics substeps (default **1000 Hz**; 250/500/2000 selectable), decoupled
from the frame rate by a time accumulator (`Sim.advance(frameDt)`). Frame dt is
clamped to 0.25 s. If a slow machine cannot keep up, substeps per frame are
capped and the simulation runs slower than real time (shown in the HUD)
rather than changing `dt`. Semi-implicit Euler for velocities, then positions
with the new velocities; angular velocity in the body frame with the full
gyroscopic term `ω × (Iω)`; orientation by the quaternion exponential map. A
non-finite state resets the run and is counted in the HUD.

### Telemetry (8 s window, sampled at 200 Hz)

* **Roll rate** (rpm) and **cumulative rotations**: unwrapped angle of the lure's
  "up" vector about the roll axis (nose axis, or entry→exit axis for
  line-through), measured from world-up. `+` = clockwise seen from behind.
* **Wobble**: dominant frequency of the yaw (heading) signal from a
  Hann-windowed DFT (a zero-crossing estimate is also available), amplitude =
  √2·std (deg).
* **Sway**: lateral CoM position, dominant frequency and √2·std amplitude (mm).
* Pitch, line angle below horizontal, depth relative to the tow point, mean
  drag (N), line tension (N), net buoyancy (g) and mass (g).
* The mini plot shows roll angle (±180°), sway and yaw over the last 10 s.

## Parameter defaults

| Parameter | Default | Notes |
|---|---|---|
| Trolling speed | 2.5 mph (1.118 m/s) | 0–6 mph |
| Water | salt, 1025 kg/m³, ν = 1.35e-6 m²/s | fresh: 1000 kg/m³, 1.14e-6 |
| Turbulence | 5 %, τ = 0.5 s, seed 1 | OU per axis |
| Surge / heave / sway | ±5 % @ 0.2 Hz / ±3 cm @ 0.25 Hz / off (0.8 Hz) | tow-point motion |
| Leader | 1.2 m, EA 600 N, ζ 0.3, Ø 0.55 mm | tension only |
| Hook / hardware | 2 g, C_dA 30 mm² | presets override |
| Material | PLA 1.24 g/cm³ | PETG, ABS, ASA, nylon, TPU, resin, custom |
| Infill / wall | 20 % / 1.2 mm | |
| Ballast | 0 g at the centre of volume | |
| C_p / C_s | 1.0 / 0.3 | advanced panel |
| C_f | 0.074 Re^-0.2 | computed each step |
| Vortex shedding | C_L0 0.25, St 0.2, ε 0.3, A 12 | advanced panel |
| Added mass | on | equivalent ellipsoid |
| Physics | 1000 Hz, 3000 elements | advanced panel |
| STL units | mm | mm, cm, inch, m |

## Assumptions and limitations

* **Quasi-steady, local pressure law.** There is no flow field. Each element
  only sees the free stream plus its own motion, with no shielding of one part
  of the body by another apart from the exposure test (so the aft body of a
  long lure is not in the wake of its nose), no pressure recovery on
  streamlined afterbodies (drag of very streamlined shapes is over-estimated)
  and no attached-flow lift (the `sin²α` law under-predicts forces on thin
  blades at small angles of attack, roughly below 15°).
* **Vortex shedding is empirical** (wake oscillator, St = 0.2 on the
  equivalent-ellipsoid thickness). It is not computed from the geometry and is
  user-tunable.
* **Added mass** comes from an equivalent ellipsoid, without Munk moment or
  fluid-acceleration (Froude–Krylov) terms; turbulence is spatially uniform
  over the lure.
* **Print model** is a uniform skin plus uniform infill. Real slicers vary top
  and bottom skins, perimeters around holes, etc. Watertightness of the print is
  assumed unless *Infill floods* is checked. Ballast and hook volumes do not
  add buoyancy.
* **Rigging**: frictionless line, no line-twist torque (swivel assumed),
  hooks/skirts are a rigid point mass + point drag at the tail (a real hook on
  a split ring swings and adds roll damping). Free surface, bottom and
  boat wake are not modelled (deep water). The leader is a straight
  spring with a lumped drag correction.
* **Symmetry**: a mirror-symmetric lure can only roll if the dynamics break the
  symmetry (turbulence and shedding seed it). A body of revolution integrated
  without element aggregation gets exactly zero roll torque. With aggregation,
  a residual drift of order 1 rpm can remain from the original triangulation.
* Explicit force evaluation: extremely light, thin parts at very high speed may
  need the 2000 Hz setting.

## Verification

Run from this folder (Node 18+; no packages needed):

```bash
node physics_check.mjs                                   # 60 s per scenario
node physics_check.mjs --quick                           # 20 s, fewer scenarios
node physics_check.mjs --stl a.stl --stl b.stl --binstl c_binary.stl
```

By default it loads `/tmp/scadcheck_<name>.stl` for the four repo lures if
they exist. To make them, run
`openscad -o /tmp/scadcheck_king_salmon_cut_plug.stl generated_models/openscad/king_salmon_cut_plug/king_salmon_cut_plug.scad`
(and the same for the others). Add `--export-format binstl` for a binary file
to pass with `--binstl`.

It checks:

* ASCII, CRLF and binary parsing, including a binary header that starts with
  `solid`, and rejection of truncated and garbage files.
* Volume and centre against trimesh reference values, and Lamb coefficients.
* Rolling of the cut-plug (line-through and eye-tied).
* No spin for a symmetric spheroid.
* Neutral-buoyancy drift.
* Bit-identical results at 30/60/144 fps and with jittered frame pacing.
* No NaNs over the run.

### Latest results (60 s per scenario, default settings: 2.5 mph, 5 % turbulence, surge + heave)

All 33 checks pass.

**Parsing.** The four repo lures parse as ASCII:

| Lure | Triangles | Physics elements |
|---|---|---|
| Cut-plug | 28 250 | 2 544 |
| Hoochie wiggler | 15 980 | 2 825 |
| Salmon spoon | 7 662 | 1 871 |
| Kite spoon | 32 724 | 1 840 |

An OpenSCAD `binstl` export of the cut-plug (1 412 584 B = 84 + 50 × 28 250)
gives the same 28 250 triangles and the same volume (29.249 cm³).

**Mass properties.** Volume and centre of volume agree with trimesh to
≤ 0.0005 % and ≤ 0.0001 mm. The cut-plug's sealed rattle void (2.30 cm³) is
subtracted, and 12.4 cm² of hole, void and socket walls are excluded from
flow loads.

| Lure | Print (20 %, 1.2 mm walls) | Hook | Displaces | Net buoyancy |
|---|---|---|---|---|
| Cut-plug | 17.3 g | 3 g | 30.0 g | **+9.7 g** (floats) |
| Hoochie wiggler | 2.8 g | 3 g | 2.9 g | −2.9 g |
| Salmon spoon | 5.2 g | 1 g | 4.35 g | −1.8 g |
| Kite spoon | 4.8 g | 1 g | 3.97 g | −1.8 g |

**Dynamics.** Roll rate is over the last 8 s; rotations are cumulative over
the 60 s run.

| Scenario | Roll rate | Rotations | Yaw wobble | Sway | Other |
|---|---|---|---|---|---|
| Repo cut-plug, **eye-tied** (auto eye = scoop centre) | **112 rpm** | **58.9** (direction chosen by noise and flipped once) | 2.27 Hz ±27° | ±60 mm | rides 312 mm above the tow point; T = 0.24 N |
| Repo cut-plug, line-through along the centreline | 112 rpm | (mechanically identical to the eye rig) | | | |
| Repo cut-plug, line-through the **diagonal** bead-chain hole (preset) | 0 rpm | 0.5 | 3.8 Hz ±5.8° | ±45 mm | rocks ±11°, tracks inverted and nose-down (−25°) 142 mm below the tow point |
| Procedural concave-face cut-plug, eye-tied | 124 rpm | 67.9 | | | |
| Same with the face skewed 12° | 131 rpm | 63.9 | | | |
| Procedural **flat**-face cut-plug, eye-tied | 0 rpm | −0.1 | 1.3 Hz ±6.8° | ±29 mm | rocks ±8°: the scoop is what drives the roll |
| Symmetric spheroid, 2.6k triangles | −0.1 rpm | 0.00 | | | rocks ±2.7° |
| Symmetric spheroid, 13.7k triangles (aggregated) | −0.9 rpm | 0.84 | | | residual from the triangulation |
| Hoochie wiggler (line-through, skirt drag) | 1 rpm | | 1.5 Hz ±21° | | rocks ±27°, pitch 44°, T = 0.53 N |
| Spoons (line-through tube) | 0 rpm | | ±3–4° | | rocks ±9–12°, T = 0.05 N |

None of the runs produced a NaN or a solver reset.

**Neutral buoyancy.** In still water a neutral spheroid drifts
0.0000 mm vertically in 30 s, because the net force is exactly 0. Trolled at
2.5 mph with no fluctuations, its depth offset is 0.02 mm and its line angle
is 0.000°. As printed (+10.3 g) it runs 119 mm above the tow point.

**Frame rate.** The spinning eye-tied cut-plug gives bit-identical state
after 20 s at 30, 60 and 144 fps and at 60 fps with ±50 % jitter: 20 000
substeps each, |Δx| = 0.000 mm, Δrpm = 0.00.

**Performance.** 2 544 elements at 1 kHz cost about 60 ms of CPU per simulated
second in Node (≈ 17× real time). The browser adds rendering of about 9k
triangles.

**Why the diagonal-hole rig does not spin in this model.** With the line
entering low on the face and the 3 g hook load at the top exit, the plug is
top-heavy. It rolls over and settles inverted, where the face lift pushes it
down and buoyancy about the off-axis line gives a strong righting moment. The
single-bevel face is mirror-symmetric, so nothing drives a continuous roll.
Tied at the scoop centre, the concave face makes the plug unstable in
roll/yaw and it spins at ~110–130 rpm. A flat face of the same angle does not.
This matches the design intent of the 6 mm scoop ("cup action").

