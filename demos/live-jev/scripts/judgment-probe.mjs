// Same states, every brain: does it answer what the question's own rule says?
// Phase 1 drives the author's rule brain (localDecide) on 3 seeds x 2 courses and samples a state every STEP s of sim time.
// Phase 2 asks each brain in BRAINS the same four questions on every state through the car server and compares with the rule.
// Usage: BRAINS=jev,llm,laya,decider,kev node scripts/judgment-probe.mjs   -> runs/judgment-probe.jsonl (one line per brain)
import fs from "node:fs";
import { World } from "../public/js/world.js";
import { Course } from "../public/js/course.js";
import { perceive } from "../public/js/sensors.js";
import { localDecide, gate, QUESTIONS } from "../public/js/brain.js";
import { CONFIG } from "../public/js/config.js";

const SERVER = process.env.SERVER || "http://127.0.0.1:3001";
const STEP = Number(process.env.STEP || 8), dt = 1 / 60;
const states = [];
for (const seed of [42, 7, 123]) for (const course of ["traffic", "gauntlet"]) {
  const world = new World(seed, new Course(seed, 1, course));
  let next = 0, nextSample = 0;
  while (world.time < 120 && !world.crashed) {
    const p = perceive(world);
    if (world.time >= nextSample) { states.push({ seed, course, t: Math.round(world.time), state: p.state }); nextSample += STEP; }
    if (world.time >= next) { world.ego.applyIntent(gate(localDecide(p.state), p.state), world.time); next = world.time + 0.4; }
    world.ego.update(dt, p.reflex, world.time); world.update(dt);
  }
}
const ref = states.map(({ state }) => { const a = localDecide(state); return { a, i: gate(a, state) }; });
console.error(`${states.length} states`);
const out = fs.createWriteStream("runs/judgment-probe.jsonl", { flags: "a" });
for (const brain of (process.env.BRAINS || "jev,llm").split(",")) {
  const rows = [];
  for (const [k, s] of states.entries()) {
    let r, j, t0, tries = 0;
    for (;;) { // upstream overload (429/5xx) is retried with backoff and logged; anything else fails the run
      t0 = Date.now();
      r = await fetch(`${SERVER}/api/${brain === "jev" ? "decide" : `${brain}-decide`}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ state: s.state, questions: QUESTIONS }) });
      j = await r.json();
      if (r.ok || !(r.status === 429 || r.status >= 500) || ++tries > 8) break;
      console.error(`\n[retry] ${brain} state ${k}: ${r.status} ${String(j.error).slice(0, 80)}`);
      await new Promise((ok) => setTimeout(ok, 5000 * tries));
    }
    if (!r.ok) throw new Error(`${brain} ${r.status}: ${j.error}`);
    const a = j.answers, i = gate(a, s.state), R = ref[k];
    const slow = s.state.ego.speed_kmh < 5;
    rows.push({ k, seed: s.seed, course: s.course, t: s.t, ms: Date.now() - t0, speed_kmh: s.state.ego.speed_kmh,
      rule: { speed: R.a.speed_action.choice, lane: R.a.lane_action.choice, ped: R.a.pedestrian_yield.noul >= CONFIG.PED_YIELD_THRESHOLD, intent: R.i.speedAction },
      brain: { speed: a.speed_action.choice, speedConf: a.speed_action.confidence, lane: a.lane_action.choice, ped: a.pedestrian_yield.noul, hazard: a.hazard.score, intent: i.speedAction, laneIntent: i.laneAction },
      stall: slow && R.i.speedAction === "speed_up" && i.speedAction !== "speed_up",
      unsafe: ["stop", "slow_down"].includes(R.i.speedAction) && i.speedAction === "speed_up" });
    process.stderr.write(".");
  }
  const n = rows.length, pct = (f) => Math.round((100 * rows.filter(f).length) / n);
  const summary = { brain, n, ms_median: rows.map((r) => r.ms).sort((x, y) => x - y)[n >> 1],
    speed_agree: pct((r) => r.brain.speed === r.rule.speed), intent_agree: pct((r) => r.brain.intent === r.rule.intent),
    lane_agree: pct((r) => r.brain.lane === r.rule.lane), ped_agree: pct((r) => (r.brain.ped >= CONFIG.PED_YIELD_THRESHOLD) === r.rule.ped),
    ped_false_alarm: pct((r) => !r.rule.ped && r.brain.ped >= CONFIG.PED_YIELD_THRESHOLD),
    stalls: rows.filter((r) => r.stall).length, stall_cases: rows.filter((r) => r.speed_kmh < 5 && r.rule.intent === "speed_up").length,
    unsafe: rows.filter((r) => r.unsafe).length, unsafe_cases: rows.filter((r) => ["stop", "slow_down"].includes(r.rule.intent)).length };
  console.error(`\n${JSON.stringify(summary)}`);
  out.write(JSON.stringify({ ...summary, rows }) + "\n");
}
out.end();
