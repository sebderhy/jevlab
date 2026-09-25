#!/bin/bash
# One Jev and one DeepSeek flight per seed, at most two browsers at a time so the physics stays at real time
# (simSpeed close to 1). Records land in runs/flights.jsonl via the dev server.
cd /home/seb/jevlab/demos/jev-autopilot
for seed in 7 123 2026; do
  MAX_MS=540000 RENDER=lite node runs/fly.mjs deepseek $seed 2>/dev/null &
  MAX_MS=540000 RENDER=lite node runs/fly.mjs jev $seed 2>/dev/null
  wait
done
MAX_MS=540000 RENDER=lite node runs/fly.mjs deepseek-json 42 2>/dev/null
echo BATCH_DONE
