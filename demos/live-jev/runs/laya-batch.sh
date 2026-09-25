#!/bin/bash
cd /home/seb/jevlab/demos/live-jev
BRAINS=laya runs/av-batch.sh
echo "== video seed 42 traffic compare3"; rm -rf runs/video-av; MAX_MS=400000 node scripts/drive.mjs compare3 42 traffic 120 runs/video-av 2>&1
echo LAYA_AV_DONE
