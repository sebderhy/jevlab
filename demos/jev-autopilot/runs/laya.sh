#!/bin/bash
cd /home/seb/jevlab/demos/jev-autopilot
echo "== laya seed 42 real time"; MAX_MS=300000 RENDER=lite node runs/fly.mjs laya 42 2>&1 | grep -v 404
echo "== laya seed 42 timescale 0.1"; rm -rf runs/video-laya; MAX_MS=1200000 TIMESCALE=0.1 RENDER=lite node runs/fly.mjs laya 42 runs/video-laya 2>&1 | grep -v 404
echo LAYA_DONE
