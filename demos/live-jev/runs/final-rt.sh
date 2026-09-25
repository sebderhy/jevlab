#!/bin/bash
# Real-time video tracks, hosted brains only (a CPU model at 30 s per decision is not a real-time test of anything). Seed 42 traffic.
cd /home/seb/jevlab/demos/live-jev
F=/home/seb/tmp/final; mkdir -p $F
for b in jev llm; do
  fr=$F/real-$b; rm -rf $fr; mkdir -p $fr
  out=$(BRAIN=$b LATENCY_SCALE=1 LATENCY_FLOOR=0.2 COURSE=traffic FRAMES=$fr SERVER=http://127.0.0.1:3001 timeout 3000 node scripts/headless.js 120 42 2>&1 | grep '^{')
  echo "$out" | sed 's/^{/{"tempo":"real","video":2,"day":"2026-09-25",/' >> runs/final.jsonl
done
echo RT_DONE
