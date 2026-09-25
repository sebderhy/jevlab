#!/bin/bash
# Same-day measurement for the two 3-track videos (24 Sept). Usage: final-runs.sh <api|local> [localBrain]
#   api:   two sequential chains in parallel, one per API (Jev, DeepSeek JSON mode): 3 seeds x 2 courses x {real, slowed},
#          seed 42 traffic recorded as frames for both videos.
#   local: the chosen local model alone on the CPU, seed 42 traffic, real then slowed, with frames.
# Output: runs/final.jsonl (one line per run, with tempo and video flags), frames in ~/tmp/final/<tempo>-<brain>.
cd /home/seb/jevlab/demos/live-jev
F=/home/seb/tmp/final; mkdir -p $F
run() { # brain scale seed course video
  local floor=${FLOOR:-0.2} tempo=$([ "$2" = 0 ] && echo slowed-${FLOOR:-0.2} || echo real) fr=""
  if [ "$5" = 1 ]; then fr="$F/$tempo-$1"; rm -rf "$fr"; mkdir -p "$fr"; fi
  out=$(BRAIN=$1 LATENCY_SCALE=$2 LATENCY_FLOOR=$floor COURSE=$4 FRAMES=$fr SERVER=http://127.0.0.1:3001 timeout 30000 node scripts/headless.js 120 $3 2>&1 | grep '^{')
  echo "$out" | sed "s/^{/{\"tempo\":\"$tempo\",\"video\":$5,\"day\":\"2026-09-24\",/" >> runs/final.jsonl
}
chain() { # brain
  for scale in 1 0; do run $1 $scale 42 traffic 1; done
  for scale in 1 0; do for seed in 42 7 123; do for course in traffic gauntlet; do
    [ "$seed/$course" = "42/traffic" ] && continue; run $1 $scale $seed $course 0; done; done; done
}
# api05: the slowed video's tracks for Jev and DeepSeek at the equal 0.5 s tempo the local model can afford
if [ "$1" = api ]; then chain jev & chain llm & wait; echo API_DONE
elif [ "$1" = api05 ]; then (FLOOR=0.5 run jev 0 42 traffic 1) & (FLOOR=0.5 run llm 0 42 traffic 1) & wait; echo API05_DONE
else run $2 1 42 traffic 1; FLOOR=0.5 run $2 0 42 traffic 1; echo LOCAL_DONE; fi
