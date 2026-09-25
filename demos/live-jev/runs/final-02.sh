#!/bin/bash
# Slowed game at the simulator's native cadence (a decision every 0.2 s of sim time, the clock stops while a brain thinks),
# seed 42 traffic, frames recorded for the "latency removed" video. Jev and DeepSeek first (minutes), then Kev (hours).
cd /home/seb/jevlab/demos/live-jev
F=/home/seb/tmp/final; mkdir -p $F
for b in jev llm kev; do
  fr=$F/slowed-$b; rm -rf $fr; mkdir -p $fr
  out=$(BRAIN=$b LATENCY_SCALE=0 LATENCY_FLOOR=0.2 COURSE=traffic FRAMES=$fr SERVER=http://127.0.0.1:3001 timeout 30000 node scripts/headless.js 120 42 2>&1 | grep '^{')
  echo "$out" | sed 's/^{/{"tempo":"slowed","video":1,"day":"2026-09-24",/' >> runs/final.jsonl
  echo "REC_DONE $b"
done
echo ALL_02_DONE
