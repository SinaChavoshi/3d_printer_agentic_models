#!/usr/bin/env node
// Headless verification for the lure simulator's physics engine.
//
// Extracts the <script id="lure-physics"> block from index.html, evaluates it in
// a node:vm context (no DOM), loads STL files, runs the simulation and prints
// telemetry plus pass/fail sanity checks.
//
// Usage:
//   node physics_check.mjs                      # default lures from /tmp/scadcheck_*.stl
//   node physics_check.mjs --seconds 30         # shorter runs
//   node physics_check.mjs --stl a.stl --stl b.stl --binstl c_binary.stl
//   node physics_check.mjs --quick              # 20 s runs, fewer scenarios
//
// Exit code is non-zero if any hard check fails.

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = { seconds: 60, quick: false, stl: [], binstl: [] };
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '--seconds') opt.seconds = parseFloat(args[++i]);
  else if (a === '--quick') opt.quick = true;
  else if (a === '--stl') opt.stl.push(args[++i]);
  else if (a === '--binstl') opt.binstl.push(args[++i]);
  else if (a === '--help' || a === '-h') {
    console.log('node physics_check.mjs [--seconds N] [--quick] [--stl file]... [--binstl file]...');
    process.exit(0);
  }
}
if (opt.quick) opt.seconds = Math.min(opt.seconds, 20);

// ---------------------------------------------------------------- load engine
const html = fs.readFileSync(path.join(here, 'index.html'), 'utf8');
const m = html.match(/<script id="lure-physics">([\s\S]*?)<\/script>/);
if (!m) { console.error('Could not find <script id="lure-physics"> in index.html'); process.exit(2); }
const context = vm.createContext({ console, TextDecoder });
vm.runInContext(m[1], context, { filename: 'index.html#lure-physics' });
const LP = context.LurePhysics;
if (!LP) { console.error('LurePhysics global was not defined'); process.exit(2); }

let failures = 0;
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`  [${ok ? 'PASS' : 'FAIL'}] ${name}${detail ? ' - ' + detail : ''}`);
  if (!ok) failures++;
}
const f = (v, d = 2) => (v === undefined || v === null || !isFinite(v) ? String(v) : v.toFixed(d));
const UNIT = 0.001;

function readBytes(p) { const b = fs.readFileSync(p); return new Uint8Array(b.buffer, b.byteOffset, b.byteLength); }
function loadModel(file, physicsTris = 3000) {
  const t0 = performance.now();
  const parsed = LP.parseSTL(readBytes(file));
  const model = LP.buildModel(parsed.positions, { unitScale: UNIT, physicsTris, renderTris: 9000, name: path.basename(file) });
  return { parsed, model, ms: performance.now() - t0 };
}
function presetRig(name) {
  const p = LP.matchPreset(name);
  if (!p) return { rig: {}, params: {} };
  return {
    preset: p,
    rig: { noseAxis: p.noseAxis, upAxis: p.upAxis, rigMode: p.rigMode, eye: p.eye || null, entry: p.entry || null, exit: p.exit || null },
    params: { hardwareMass: p.hardwareMass / 1000, hardwareCdA: p.hardwareCdA * 1e-6 },
  };
}

// Run with a given frame pacing through sim.advance (the exact path the browser uses).
function runPaced(sim, seconds, fps, jitter = 0, seed = 7) {
  let s = seed >>> 0;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  let t = 0;
  let maxAbs = 0;
  while (t < seconds - 1e-9) {
    let dt = 1 / fps;
    if (jitter) dt *= 1 + jitter * (rnd() * 2 - 1);
    dt = Math.min(dt, seconds - t);
    sim.advance(dt);
    t += dt;
    const st = sim.s;
    for (const v of [...st.x, ...st.v, ...st.q, ...st.w]) if (!isFinite(v)) maxAbs = Infinity;
  }
  return maxAbs;
}
function telemetryLine(label, tm) {
  return `${label.padEnd(34)} roll ${f(tm.rollRpm, 0).padStart(5)} rpm | rot ${f(tm.rotations, 1).padStart(6)} | yaw ${f(tm.wobbleHz, 2)} Hz ±${f(tm.yawAmpDeg, 1)}° | sway ${f(tm.swayHz, 2)} Hz ±${f(tm.swayAmpMm, 1)} mm | pitch ${f(tm.pitchMeanDeg, 1)}° | line ${f(tm.lineAngleDeg, 1)}° | depth ${f(tm.depthMm, 0)} mm | drag ${f(tm.dragN, 3)} N | T ${f(tm.tensionN, 3)} N | net ${f(tm.netBuoyancyG, 1)} g`;
}
function allFinite(sim) {
  const st = sim.s;
  return [...st.x, ...st.v, ...st.q, ...st.w].every(Number.isFinite) && sim.nanResets === 0;
}

// ------------------------------------------------------------------ 1. parsing
console.log('\n=== 1. STL parsing ===');
const defaults = {
  cutplug: '/tmp/scadcheck_king_salmon_cut_plug.stl',
  wiggler: '/tmp/scadcheck_fishing_hoochie_wiggler.stl',
  salmonSpoon: '/tmp/scadcheck_salmon_fishing_spoon.stl',
  kiteSpoon: '/tmp/scadcheck_fishing_spoon.stl',
};
const files = opt.stl.length ? opt.stl : Object.values(defaults).filter((p) => fs.existsSync(p));
if (!files.length) console.log('  (no STL files found; pass --stl paths)');
const models = {};
for (const file of files) {
  try {
    const { parsed, model, ms } = loadModel(file);
    models[file] = { parsed, model };
    const sz = model.bbox.size.map((v) => (v * 1000).toFixed(1)).join(' x ');
    console.log(`  ${path.basename(file)}: ${parsed.format}, ${parsed.triCount} tris -> phys ${model.phys.count}, render ${model.render.nF}; ` +
      `V=${(model.integ.V * 1e6).toFixed(3)} cm3, A=${(model.integ.A * 1e4).toFixed(2)} cm2, size ${sz} mm, hidden ${(model.phys.hiddenArea * 1e4).toFixed(2)} cm2, ${ms.toFixed(0)} ms`);
    check(`ASCII parse ${path.basename(file)}`, parsed.triCount > 100 && parsed.format === 'ascii', `${parsed.triCount} facets`);
  } catch (e) {
    check(`parse ${path.basename(file)}`, false, e.message);
  }
}
// CRLF variant + binary round-trip + truncation, using the first model
if (files.length) {
  const file = files[0];
  const text = fs.readFileSync(file, 'utf8');
  const crlf = new TextEncoder().encode(text.replace(/\r?\n/g, '\r\n'));
  const a = LP.parseSTL(crlf);
  check('ASCII with CRLF line endings', a.triCount === models[file].parsed.triCount, `${a.triCount} facets`);
  const bin = new Uint8Array(LP.toBinarySTL(models[file].parsed.positions, 'solid looks-like-ascii header'));
  const b = LP.parseSTL(bin);
  check('binary round-trip (header starts with "solid")', b.format === 'binary' && b.triCount === a.triCount, `${b.triCount} tris, ${bin.byteLength} bytes`);
  let err = '';
  try { LP.parseSTL(bin.slice(0, bin.byteLength - 37)); } catch (e) { err = e.message; }
  check('truncated binary rejected', /truncated/i.test(err), err.slice(0, 90));
  err = '';
  try { LP.parseSTL(new TextEncoder().encode('hello world, not an stl file at all')); } catch (e) { err = e.message; }
  check('garbage rejected', err.length > 0, err.slice(0, 80));
}
for (const bf of opt.binstl) {
  try {
    const parsed = LP.parseSTL(readBytes(bf));
    const model = LP.buildModel(parsed.positions, { unitScale: UNIT, physicsTris: 3000 });
    const asciiTwin = Object.keys(models).find((k) => path.basename(k).replace(/\.stl$/, '').replace(/^scadcheck_/, '') === path.basename(bf).replace(/(_bin(ary)?)?\.stl$/, '').replace(/^scadcheck_/, ''));
    let detail = `${parsed.format}, ${parsed.triCount} tris, V=${(model.integ.V * 1e6).toFixed(3)} cm3`;
    let ok = parsed.format === 'binary' && parsed.triCount > 100;
    if (asciiTwin) {
      const va = models[asciiTwin].model.integ.V;
      detail += ` (ASCII twin V=${(va * 1e6).toFixed(3)} cm3, tris ${models[asciiTwin].parsed.triCount})`;
      ok = ok && Math.abs(model.integ.V - va) / va < 1e-4;
    }
    check(`OpenSCAD binary STL ${path.basename(bf)}`, ok, detail);
  } catch (e) {
    check(`OpenSCAD binary STL ${path.basename(bf)}`, false, e.message);
  }
}

// ---------------------------------------------------------- 2. mass properties
console.log('\n=== 2. Mass properties (signed tetrahedra) ===');
const refs = { // trimesh reference values (volume cm3, centre of volume mm)
  king_salmon_cut_plug: { V: 29.2491, c: [54.4443, 0, 0.5241] },
  fishing_hoochie_wiggler: { V: 2.8625, c: [3.8092, 17.1831, 7.0] },
  salmon_fishing_spoon: { V: 4.2461, c: [-0.0068, -1.6499, -3.0487] },
  fishing_spoon: { V: 3.8696, c: [-0.0125, -1.9218, -1.2115] },
};
for (const file of Object.keys(models)) {
  const { model } = models[file];
  const key = Object.keys(refs).find((k) => path.basename(file).includes(k) && !(k === 'fishing_spoon' && file.includes('salmon')));
  const { rig, params } = presetRig(path.basename(file));
  const sim = new LP.Sim(model, params, rig);
  const pr = sim.props;
  const cv = pr.cob.map((v) => v * 1000);
  console.log(`  ${path.basename(file)}: V=${(pr.volume * 1e6).toFixed(3)} cm3, CoV=(${cv.map((v) => v.toFixed(2)).join(', ')}) mm, ` +
    `mass=${(pr.mass * 1000).toFixed(2)} g (print ${(pr.mPrint * 1000).toFixed(2)} + hook ${(pr.mHardware * 1000).toFixed(2)}), ` +
    `displaces ${(pr.displacedMass * 1000).toFixed(2)} g -> net ${(pr.netBuoyancyKg * 1000).toFixed(2)} g (${pr.floats > 0 ? 'floats' : pr.floats < 0 ? 'sinks' : 'neutral'}), ` +
    `CoM=(${pr.com.map((v) => (v * 1000).toFixed(2)).join(', ')}) mm`);
  if (sim.body.added) {
    const am = sim.body.added;
    console.log(`     ellipsoid semi-axes ${model.ellipsoid.axes.map((v) => (v * 1000).toFixed(1)).join('/')} mm, Lamb alpha sum=${(am.alpha[0] + am.alpha[1] + am.alpha[2]).toFixed(4)}, ` +
      `added mass ${am.mt.map((v) => (v * 1000).toFixed(1)).join('/')} g`);
  }
  if (key) {
    const r = refs[key];
    const dv = Math.abs(pr.volume * 1e6 - r.V) / r.V;
    const dc = Math.hypot(cv[0] - r.c[0], cv[1] - r.c[1], cv[2] - r.c[2]);
    check(`volume & centre vs trimesh (${key})`, dv < 1e-3 && dc < 0.05, `dV=${(dv * 100).toFixed(4)} %, dC=${dc.toFixed(4)} mm`);
  }
}
{
  // analytic checks on a finely tessellated procedural spheroid (faceting error ~0.25 %)
  const model = LP.buildModel(LP.makeEllipsoidPositions(40, 11, 96, 72), { unitScale: UNIT, physicsTris: 3000 });
  const Vexact = 4 / 3 * Math.PI * 0.040 * 0.011 * 0.011;
  check('spheroid volume vs analytic', Math.abs(model.integ.V - Vexact) / Vexact < 0.01, `${(model.integ.V * 1e6).toFixed(3)} vs ${(Vexact * 1e6).toFixed(3)} cm3`);
  const al = LP.lambCoefficients([1, 1, 1]);
  const am = LP.ellipsoidAddedMass([1, 1, 1], 1);
  check('Lamb coefficients for a sphere (alpha=2/3, k=0.5)', Math.abs(al[0] - 2 / 3) < 1e-3 && Math.abs(am.mt[0] - 0.5) < 2e-3, `alpha=${al[0].toFixed(4)}, k=${am.mt[0].toFixed(4)}`);
}

// ------------------------------------------------------------- 3. dynamics
console.log(`\n=== 3. Dynamics: ${opt.seconds} s per scenario at default settings (2.5 mph, 5 % turbulence, surge+heave on) ===`);
const scen = [];
const demoCut = LP.buildModel(LP.makeCutPlugPositions({}), { unitScale: UNIT, physicsTris: 3000, name: 'demo_cut_plug' });
const demoSkew = LP.buildModel(LP.makeCutPlugPositions({ skewDeg: 12 }), { unitScale: UNIT, physicsTris: 3000, name: 'demo_cut_plug_skew12' });
const demoFlat = LP.buildModel(LP.makeCutPlugPositions({ dish: 0 }), { unitScale: UNIT, physicsTris: 3000, name: 'demo_cut_plug_flat' });
const ellipsoid = LP.buildModel(LP.makeEllipsoidPositions(40, 11), { unitScale: UNIT, physicsTris: 3000, name: 'ellipsoid' });
const ellipsoidFine = LP.buildModel(LP.makeEllipsoidPositions(40, 11, 96, 72), { unitScale: UNIT, physicsTris: 3000, name: 'ellipsoid_fine' });
console.log(`  spheroid controls: coarse ${ellipsoid.full.nF} tris -> ${ellipsoid.phys.count} elements (no aggregation); fine ${ellipsoidFine.full.nF} tris -> ${ellipsoidFine.phys.count} elements (aggregated)`);
const demoRig = { noseAxis: '-x', upAxis: '+z', rigMode: 'through', entry: [24, 0, -5], exit: [46, 0, 11.2] };
const eyeRig = { noseAxis: '-x', upAxis: '+z', rigMode: 'eye' };
const cutFile = Object.keys(models).find((k) => /cut_plug/.test(k));
if (cutFile) {
  const pr = presetRig(path.basename(cutFile));
  scen.push({ label: 'cut-plug, line-through (preset hole)', model: models[cutFile].model, rig: pr.rig, params: pr.params, group: 'cutplug' });
  scen.push({ label: 'cut-plug, eye-tied (auto eye)', model: models[cutFile].model, rig: { ...pr.rig, rigMode: 'eye' }, params: pr.params, group: 'cutplug' });
  scen.push({ label: 'cut-plug, line-through on centreline', model: models[cutFile].model, rig: { ...pr.rig, entry: null, exit: null }, params: pr.params, group: 'cutplug' });
}
scen.push({ label: 'symmetric spheroid, eye-tied', model: ellipsoid, rig: eyeRig, params: {}, expect: 'nospin' });
scen.push({ label: 'symmetric spheroid (fine mesh)', model: ellipsoidFine, rig: eyeRig, params: {}, expect: 'nospin' });
if (!opt.quick) {
  scen.push({ label: 'demo cut-plug, line-through', model: demoCut, rig: demoRig, params: { hardwareMass: 0.003, hardwareCdA: 40e-6 } });
  scen.push({ label: 'demo cut-plug, eye-tied', model: demoCut, rig: eyeRig, params: { hardwareMass: 0.003, hardwareCdA: 40e-6 } });
  scen.push({ label: 'demo cut-plug FLAT face, eye-tied', model: demoFlat, rig: eyeRig, params: { hardwareMass: 0.003, hardwareCdA: 40e-6 } });
  scen.push({ label: 'demo cut-plug 12 deg skew, eye-tied', model: demoSkew, rig: eyeRig, params: { hardwareMass: 0.003, hardwareCdA: 40e-6 } });
  for (const file of Object.keys(models)) {
    if (file === cutFile) continue;
    const pr = presetRig(path.basename(file));
    scen.push({ label: path.basename(file).replace('scadcheck_', '').replace('.stl', '') + ' (preset)', model: models[file].model, rig: pr.rig, params: pr.params });
  }
}
const dynResults = {};
for (const sc of scen) {
  const sim = new LP.Sim(sc.model, sc.params, sc.rig);
  const t0 = performance.now();
  runPaced(sim, opt.seconds, 60);
  const ms = performance.now() - t0;
  const tm = sim.telemetry(8);
  dynResults[sc.label] = { tm, sim, sc };
  console.log('  ' + telemetryLine(sc.label, tm) + ` | rock ±${f(tm.rollAmpDeg, 0)}° | ${(opt.seconds / (ms / 1000)).toFixed(1)}x RT`);
  check(`no NaN / solver reset over ${opt.seconds} s: ${sc.label}`, allFinite(sim), `nanResets=${sim.nanResets}`);
  if (sc.expect === 'nospin') {
    check(`does NOT spin: ${sc.label}`, Math.abs(tm.rollRpm) < 5 && Math.abs(tm.rotations) < 2,
      `${f(tm.rollRpm, 1)} rpm, ${f(tm.rotations, 2)} rotations in ${opt.seconds} s, roll rocking ±${f(tm.rollAmpDeg, 1)}°`);
  }
}
const spins = (tm) => Math.abs(tm.rollRpm) > 20 || Math.abs(tm.rotations) > 10;
const cutRuns = Object.values(dynResults).filter((r) => r.sc.group === 'cutplug');
if (cutRuns.length) {
  const detail = cutRuns.map((r) => `${r.sc.label.replace('cut-plug, ', '')}: ${f(r.tm.rollRpm, 0)} rpm / ${f(r.tm.rotations, 1)} rev${spins(r.tm) ? ' (spins)' : ' (no spin)'}`).join('; ');
  check('cut-plug rolls/spins at trolling speed (line-through or eye-tied)', cutRuns.some((r) => spins(r.tm)), detail);
}

// -------------------------------------------------------- 4. neutral buoyancy
console.log('\n=== 4. Neutral buoyancy -> zero net vertical force ===');
{
  const quiet = { turbIntensity: 0, surgeFrac: 0, heaveAmp: 0, swayAmp: 0, vortexCL: 0, buoyancyMode: 'neutral', hardwareMass: 0, hardwareCdA: 0 };
  // (a) still water: slack line, lure must neither sink nor rise
  const simA = new LP.Sim(ellipsoid, { ...quiet, speed: 0 }, { noseAxis: '-x', upAxis: '+z', rigMode: 'eye' });
  const y0 = simA.s.x[1];
  simA.runFor(30);
  const driftA = (simA.s.x[1] - y0) * 1000;
  check('neutral spheroid in still water: vertical drift over 30 s', Math.abs(driftA) < 1 && Math.abs(simA.props.netBuoyancyKg) < 1e-9,
    `${driftA.toFixed(4)} mm, net force ${(simA.props.netBuoyancyKg * 9.80665).toExponential(2)} N`);
  // (b) trolled at 2.5 mph with no fluctuations: lure should run level with the tow point
  const simB = new LP.Sim(ellipsoid, { ...quiet }, { noseAxis: '-x', upAxis: '+z', rigMode: 'eye' });
  simB.runFor(30);
  const tB = simB.telemetry(8);
  check('neutral spheroid trolled at 2.5 mph: depth offset', Math.abs(tB.depthMm) < 2, `depth ${f(tB.depthMm, 2)} mm, line angle ${f(tB.lineAngleDeg, 3)}°`);
  // (c) "As printed" for comparison
  const simC = new LP.Sim(ellipsoid, { ...quiet, buoyancyMode: 'printed' }, { noseAxis: '-x', upAxis: '+z', rigMode: 'eye' });
  simC.runFor(30);
  const tC = simC.telemetry(8);
  console.log(`     (as-printed spheroid: net ${f(tC.netBuoyancyG, 2)} g -> runs ${f(-tC.depthMm, 1)} mm above the tow point, line ${f(tC.lineAngleDeg, 2)}°)`);
}

// ------------------------------------------------- 5. frame-rate independence
console.log('\n=== 5. Frame-rate independence (same seed, sim.advance at different frame rates; spinning eye-tied cut-plug) ===');
{
  let target;
  if (cutFile) {
    const pr = presetRig(path.basename(cutFile));
    target = { model: models[cutFile].model, params: pr.params, rig: { ...pr.rig, rigMode: 'eye' } };
  } else {
    target = { model: demoCut, rig: eyeRig, params: {} };
  }
  const T = Math.min(20, opt.seconds);
  const rows = [];
  for (const [fps, jit] of [[30, 0], [60, 0], [144, 0], [60, 0.5]]) {
    const sim = new LP.Sim(target.model, target.params, target.rig);
    runPaced(sim, T, fps, jit);
    rows.push({ fps, jit, tm: sim.telemetry(8), x: sim.s.x.slice(), steps: Math.round(sim.s.t / sim.dt), t: sim.s.t });
  }
  for (const r of rows) console.log(`  ${String(r.fps).padStart(3)} fps${r.jit ? ' (±50% jitter)' : '              '}: t=${r.t.toFixed(4)} s, steps=${r.steps}, ` + telemetryLine('', r.tm).trim());
  const base = rows[1];
  let maxDx = 0;
  let maxRpm = 0;
  for (const r of rows) {
    maxRpm = Math.max(maxRpm, Math.abs(r.tm.rollRpm - base.tm.rollRpm));
    maxDx = Math.max(maxDx, Math.hypot(r.x[0] - base.x[0], r.x[1] - base.x[1], r.x[2] - base.x[2]));
  }
  const sameSteps = rows.every((r) => r.steps === base.steps);
  check('identical physics across 30/60/144 fps and jittered frames', maxDx < 2e-3 && maxRpm < 1,
    `max |dx| ${(maxDx * 1000).toFixed(3)} mm, max |d rpm| ${maxRpm.toFixed(2)}, ${sameSteps ? 'same substep count' : 'substep counts differ by <=1'} (fixed dt + accumulator)`);
}

// ---------------------------------------------------------- 6. performance
console.log('\n=== 6. Performance ===');
{
  const model = cutFile ? models[cutFile].model : demoCut;
  const sim = new LP.Sim(model, {}, cutFile ? presetRig(path.basename(cutFile)).rig : demoRig);
  const t0 = performance.now();
  sim.runFor(5);
  const ms = performance.now() - t0;
  console.log(`  ${sim.body.n} faces @ ${Math.round(1 / sim.dt)} Hz: ${(ms / 5).toFixed(1)} ms per simulated second (${(5000 / ms).toFixed(1)}x real time in node)`);
}

console.log(`\n${failures ? 'FAILED' : 'ALL CHECKS PASSED'}: ${results.filter((r) => r.ok).length}/${results.length} checks passed.`);
process.exit(failures ? 1 : 0);
