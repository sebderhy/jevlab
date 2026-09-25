# jev-autopilot fork notes

Upstream: https://github.com/arielweinberger/jev-autopilot, commit `3292bbc6acfa2bcc8a4373c984f6420af5f47fd1` (17 Sept 2026), MIT (declared in `package.json`).

Added here: `server/deepseek.ts` (DeepSeek V4.1 Flash pilot on Fireworks, logprob and JSON recipes, `?pilot=deepseek` / `deepseek-json`), `server/laya.ts` (a local Laya or Decider pilot through jevlab's `/decide` API), a flight log in the HUD, `runs/fly.mjs` (fly one mission headless, optionally recording video) and `runs/flights.jsonl` (every flight behind the deck's drone slide). `scripts/probe.mjs` sends one telemetry frame to a pilot and prints its answers.
