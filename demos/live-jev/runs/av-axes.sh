#!/bin/bash
# Axis-splitting AV runs (latency vs judgment vs input modality). Each line of runs/av-axes.jsonl is one
# 120 sim-second run. CONFIGS entries: "<brain> <LATENCY_SCALE> <LATENCY_FLOOR> <seeds>".
cd /home/seb/jevlab/demos/live-jev
run() { # brain scale floor seed course
  out=$(BRAIN=$1 LATENCY_SCALE=$2 LATENCY_FLOOR=$3 COURSE=$5 SERVER=http://127.0.0.1:3001 timeout 3000 node scripts/headless.js 120 $4 2>&1 | grep '^{')
  echo "$out" >> runs/av-axes.jsonl
}
wave() { # each arg: "brain scale floor"
  for cfg in "$@"; do set -- $cfg; for course in traffic gauntlet; do for seed in 42 7 123; do run $1 $2 $3 $seed $course & done; done; done
  wait
}
wave "llm 0 0.2" "jev 1 1.35" "llm-vision 1 0.2"
echo WAVE1_DONE
wave "llm-vision-state 1 0.2" "llm-vision 0 0.2"
echo WAVE2_DONE
wave "llm-vision-state 0 0.2"
echo WAVE3_DONE
