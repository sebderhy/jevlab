#!/bin/bash
# Four seed-42 gauntlet runs with frame capture for the axis-split video (runs/av-axes-video.jsonl).
cd /home/seb/jevlab/demos/live-jev
V=/home/seb/tmp/av-video
run() { # name brain scale
  out=$(FRAMES=$V/$1 BRAIN=$2 LATENCY_SCALE=$3 COURSE=gauntlet SERVER=http://127.0.0.1:3001 timeout 3000 node scripts/headless.js 120 42 2>&1 | grep '^{')
  echo "{\"track\":\"$1\",$(echo "$out" | cut -c2-)" >> runs/av-axes-video.jsonl
}
run jev jev 1 & run llm-real llm 1 & run llm-slow llm 0 & run llm-vision llm-vision 1 &
wait
echo AV_VIDEO_DONE
