#!/bin/bash
# Equal-tempo batch at a decision every 0.5 s of sim time (the slowed video's tempo), seed 42 traffic excluded (recorded already).
# Usage: final-05.sh <jev|llm>
cd /home/seb/jevlab/demos/live-jev
for seed in 42 7 123; do for course in traffic gauntlet; do
  [ "$seed/$course" = "42/traffic" ] && continue
  out=$(BRAIN=$1 LATENCY_SCALE=0 LATENCY_FLOOR=0.5 COURSE=$course SERVER=http://127.0.0.1:3001 timeout 20000 node scripts/headless.js 120 $seed 2>&1 | grep '^{')
  echo "$out" | sed 's/^{/{"tempo":"slowed-0.5","video":0,"day":"2026-09-24",/' >> runs/final.jsonl
done; done
echo "DONE_05 $1"
