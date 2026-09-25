#!/bin/bash
# Laya at the slowed-game tempo (judgment only), seed 42, both courses, sequential (one CPU model).
cd /home/seb/jevlab/demos/live-jev
for course in traffic gauntlet; do
  out=$(BRAIN=laya LATENCY_SCALE=0 LATENCY_FLOOR=0.2 COURSE=$course SERVER=http://127.0.0.1:3001 timeout 3000 node scripts/headless.js 120 42 2>&1 | grep '^{')
  echo "$out" >> runs/av-axes.jsonl
done
echo LAYA_AXES_DONE
