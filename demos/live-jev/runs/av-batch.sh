#!/bin/bash
# Headless AV runs: each brain drives 120 sim seconds per seed and course; JSON summaries append to runs/av.jsonl.
cd /home/seb/jevlab/demos/live-jev
brains="${BRAINS:-jev llm}"
for course in traffic gauntlet; do
  for seed in 42 7 123; do
    for b in $brains; do
      ( out=$(BRAIN=$b COURSE=$course SERVER=http://127.0.0.1:3001 timeout 900 node scripts/headless.js 120 $seed 2>&1 | grep '^{'); echo "{\"brain\":\"$b\",$(echo "$out" | cut -c2-)" >> runs/av.jsonl ) &
    done
    wait
  done
done
echo AV_BATCH_DONE
