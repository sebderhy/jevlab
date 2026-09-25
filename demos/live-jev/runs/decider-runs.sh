#!/bin/bash
# Decider-2B (packed layout, CPU) in the car and drone demos, seed 42. Car: slowed game (judgment only), frames recorded for the
# 3-track video; Jev and DeepSeek at real tempo re-recorded first on the same traffic course. Drone: real time, then timescale 0.1.
cd /home/seb/jevlab/demos/live-jev
F=/home/seb/tmp/av-decider
for spec in "jev 1 0.2 jev" "llm 1 0.2 llm-real"; do set -- $spec
  rm -rf $F/$4; mkdir -p $F/$4
  out=$(BRAIN=$1 LATENCY_SCALE=$2 LATENCY_FLOOR=$3 COURSE=traffic FRAMES=$F/$4 SERVER=http://127.0.0.1:3001 timeout 3000 node scripts/headless.js 120 42 2>&1 | grep '^{')
  echo "$out" | sed "s/^{/{\"track\":\"$4\",/" >> runs/av-decider-video.jsonl
done
rm -rf $F/decider; mkdir -p $F/decider
out=$(BRAIN=decider LATENCY_SCALE=0 LATENCY_FLOOR=0.2 COURSE=traffic FRAMES=$F/decider SERVER=http://127.0.0.1:3001 timeout 20000 node scripts/headless.js 120 42 2>&1 | grep '^{')
echo "$out" | sed 's/^{/{"track":"decider-slow",/' >> runs/av-decider-video.jsonl
echo "$out" >> runs/av-axes.jsonl
echo CAR_TRAFFIC_DONE
out=$(BRAIN=decider LATENCY_SCALE=0 LATENCY_FLOOR=0.2 COURSE=gauntlet SERVER=http://127.0.0.1:3001 timeout 20000 node scripts/headless.js 120 42 2>&1 | grep '^{')
echo "$out" >> runs/av-axes.jsonl
echo CAR_GAUNTLET_DONE
cd /home/seb/jevlab/demos/jev-autopilot
echo "== decider seed 42 real time"; MAX_MS=300000 RENDER=lite node runs/fly.mjs decider 42 2>&1 | grep -v 404
echo "== decider seed 42 timescale 0.1"; MAX_MS=1500000 TIMESCALE=0.1 RENDER=lite node runs/fly.mjs decider 42 2>&1 | grep -v 404
echo DECIDER_RUNS_DONE
