import * as THREE from 'three';
import { createWorld } from './world';
import { Drone } from './drone';
import { ManualInput } from './input';
import { Hud } from './hud';
import { Autopilot } from './autopilot';
import type { Sticks, Telemetry, PilotName } from './types';
import { PILOTS, costUsd } from './types';

const CRUISE_ALT = 30;

const canvas = document.getElementById('scene') as HTMLCanvasElement;
// ?render=lite halves the resolution and drops shadows so software (CPU) rendering keeps the physics at real time.
const lite = new URLSearchParams(location.search).get('render') === 'lite';
const renderer = new THREE.WebGLRenderer({ canvas, antialias: !lite });
renderer.setPixelRatio(lite ? 0.5 : Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = !lite;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const world = createWorld();
const drone = new Drone(world);
world.scene.add(drone.group);

const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.1, 900);

addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});

// ?pilot=jev|deepseek|deepseek-json picks the model, ?auto=1 hands it the sticks at load (for recordings).
const params = new URLSearchParams(location.search);
const pilotParam = params.get('pilot') ?? 'jev';
if (!(pilotParam in PILOTS)) throw new Error(`unknown pilot "${pilotParam}"`);
const pilot = pilotParam as PilotName;
// ?timescale=0.1 runs the physics at a tenth of wall-clock speed: a 3 s pilot then sees the world as a 300 ms pilot would.
const timescale = Number(params.get('timescale') ?? 1);
if (!(timescale > 0 && timescale <= 1)) throw new Error('timescale must be in (0, 1]');
const hud = new Hud();
hud.pilot = pilot;
const input = new ManualInput();
const autopilot = new Autopilot(pilot, 180, timescale);
let simSeconds = 0;
let flightLogged = false;
let mode: 'manual' | 'auto' = 'manual';
let missionDone = false;
let bannerRequests = -1; // how many Jev decisions the landing banner currently reflects

autopilot.onResponse = (r) => hud.setJev(r);
autopilot.onError = (e) => hud.setJev(null, e);

function setMode(m: 'manual' | 'auto') {
  mode = m;
  hud.setMode(m);
  if (m === 'auto') {
    autopilot.reset();
    hud.setJev(null);
    simSeconds = 0;
    flightLogged = false;
    hud.flash(`${PILOTS[pilot].short.toUpperCase()} HAS CONTROL`, 'ok', 1500);
  } else {
    hud.flash('MANUAL', '', 1000);
  }
}

function resetMission() {
  drone.reset();
  autopilot.reset();
  missionDone = false;
  hud.clearFlash();
  hud.flash('TAKE OFF FROM A → LAND ON B', '', 3000);
}

input.onKey = (code) => {
  if (code === 'KeyJ') setMode(mode === 'auto' ? 'manual' : 'auto');
  if (code === 'KeyR') resetMission();
};

function showLandingBanner() {
  const st = autopilot.stats;
  const flightSeconds = ((st.endedAt || performance.now()) - st.startedAt) / 1000;
  const sub =
    mode === 'auto' && st.requests > 0
      ? `${PILOTS[pilot].short.toUpperCase()}: ${(st.inputTokens + st.outputTokens).toLocaleString()} TOKENS · $${costUsd(pilot, st.inputTokens, st.outputTokens).toFixed(4)} · ${st.requests} DECISIONS · ${flightSeconds.toFixed(0)} S · IN ${st.inputTokens.toLocaleString()} / OUT ${st.outputTokens.toLocaleString()}`
      : undefined;
  bannerRequests = st.requests;
  hud.flash(`LANDED ON B · ${drone.landingSpeed.toFixed(1)} m/s`, 'ok', 0, sub);
}

function buildTelemetry(): Telemetry {
  const fwd = drone.forward();
  const rgt = drone.right();
  const toPad = new THREE.Vector3(world.landingPad.x - drone.position.x, 0, world.landingPad.z - drone.position.z);
  const padForward = toPad.dot(fwd);
  const padRight = toPad.dot(rgt);
  const bearing = THREE.MathUtils.radToDeg(Math.atan2(padRight, padForward));
  const tallest = drone.tallestOnPath();
  return {
    phase: drone.phase,
    altitude: drone.altitude,
    verticalSpeed: drone.velocity.y,
    groundSpeed: Math.hypot(drone.velocity.x, drone.velocity.z),
    distanceToPad: drone.distanceToPad(),
    bearingToPad: bearing,
    padForward,
    padRight,
    velocityForward: drone.velocity.dot(fwd),
    velocityRight: drone.velocity.dot(rgt),
    obstacleAhead: drone.obstacleAhead(),
    tallestObstacleOnPath: tallest,
    // Cruise clears whatever is on the direct line to the pad.
    cruiseAltitude: Math.max(CRUISE_ALT, tallest + 8),
    padRadius: world.padRadius,
  };
}

function updateCamera() {
  // Third person chase camera: behind and above the drone, smoothed
  const behind = drone.forward().multiplyScalar(-6);
  const desired = drone.position.clone().add(behind).add(new THREE.Vector3(0, 2.2, 0));
  camera.position.lerp(desired, 0.12);
  camera.lookAt(drone.position.clone().add(new THREE.Vector3(0, 0.3, 0)));
}

/** Simulated seconds per wall second since the autopilot took over; below 1 means rendering slowed the physics. */
function simSpeed() {
  const wall = ((autopilot.stats.endedAt || performance.now()) - autopilot.stats.startedAt) / 1000;
  return wall > 0 ? simSeconds / wall : 1;
}

/** One record per finished flight, appended server-side to runs/flights.jsonl and exposed as window.__flight. */
function logFlight() {
  const st = autopilot.stats;
  if (!st.endedAt) st.endedAt = performance.now();
  const flight = {
    pilot,
    seed: world.seed,
    timescale,
    outcome: drone.phase === 'crashed' ? 'crashed' : drone.onPad() ? 'landed_on_pad' : drone.distanceToPad() < 2 * world.padRadius ? 'landed_off_pad' : 'landed_wrong_spot',
    landingSpeed: Number(drone.landingSpeed.toFixed(2)),
    distanceToPad: Number(drone.distanceToPad().toFixed(1)),
    wallSeconds: Number(((st.endedAt - st.startedAt) / 1000).toFixed(1)),
    simSeconds: Number(simSeconds.toFixed(1)),
    simSpeed: Number(simSpeed().toFixed(2)),
    decisions: st.requests,
    stale: st.stale,
    errors: st.errors,
    avgLatencyMs: st.requests ? Math.round(st.latencyMsTotal / st.requests) : null,
    inputTokens: st.inputTokens,
    outputTokens: st.outputTokens,
    costUsd: Number(costUsd(pilot, st.inputTokens, st.outputTokens).toFixed(5)),
  };
  (window as unknown as { __flight: unknown }).__flight = flight;
  void fetch('/api/flight', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(flight) });
}

let last = performance.now();
let telemetry = buildTelemetry();
function frame(now: number) {
  const dt = Math.min(0.05, (now - last) / 1000) * timescale;
  last = now;

  telemetry = buildTelemetry();
  let sticks: Sticks;
  if (mode === 'auto') {
    // Any manual input snatches control back
    const manual = input.read(dt);
    if (Math.abs(manual.throttle) + Math.abs(manual.yaw) + Math.abs(manual.pitch) + Math.abs(manual.roll) > 0.5) {
      setMode('manual');
      sticks = manual;
    } else {
      sticks = autopilot.update(now, dt, telemetry);
    }
  } else {
    sticks = input.read(dt);
  }

  drone.step(dt, sticks);
  if (mode === 'auto' && !missionDone) simSeconds += dt;

  if (!missionDone) {
    if (drone.phase === 'landed') {
      missionDone = true;
      if (drone.onPad()) showLandingBanner();
      else if (drone.distanceToPad() < 2 * world.padRadius) hud.flash('LANDED · JUST OFF THE PAD', '', 0);
      else hud.flash('LANDED · WRONG SPOT', 'bad', 0);
    } else if (drone.phase === 'crashed') {
      missionDone = true;
      hud.flash('CRASHED · PRESS R', 'bad', 0);
    }
  }

  // The final "cut motors" answer arrives just after touchdown; keep the banner totals exact.
  if (missionDone && drone.phase === 'landed' && mode === 'auto' && drone.onPad() && autopilot.stats.requests !== bannerRequests) {
    showLandingBanner();
  }

  if (missionDone && mode === 'auto' && !flightLogged && (drone.phase === 'crashed' || autopilot.motorsCut || drone.phase === 'landed')) {
    flightLogged = true;
    logFlight();
  }

  updateCamera();
  if (mode === 'auto') hud.setFlightStats(autopilot.stats, simSpeed());
  // Live snapshot for the headless runner, so a flight that never ends still reports where it got to.
  (window as unknown as { __status: unknown }).__status = { phase: drone.phase, altitude: Number(drone.altitude.toFixed(1)), distanceToPad: Number(drone.distanceToPad().toFixed(1)), simSeconds: Number(simSeconds.toFixed(1)), decisions: autopilot.stats.requests, stale: autopilot.stats.stale, errors: autopilot.stats.errors, landingCommitted: autopilot.landingCommitted };
  hud.setSticks(sticks, mode, drone.motorsOn);
  hud.setTelemetry({
    alt: drone.altitude,
    vs: drone.velocity.y,
    spd: telemetry.groundSpeed,
    dist: telemetry.distanceToPad,
    hdg: drone.headingDeg,
    phase: drone.phase,
    bearing: telemetry.bearingToPad,
  });

  renderer.render(world.scene, camera);
  requestAnimationFrame(frame);
}

resetMission();
hud.setMode('manual');
document.getElementById('seed')!.textContent = String(world.seed);
document.getElementById('pilot-name')!.textContent = pilot;
requestAnimationFrame(frame);
if (params.get('auto') === '1') setTimeout(() => setMode('auto'), 1000);
