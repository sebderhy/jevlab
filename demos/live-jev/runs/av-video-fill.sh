#!/bin/bash
# Fill any gap in a captured frame sequence by linking each missing frame to the previous one.
for d in "$@"; do prev=""; for n in $(seq 0 3600); do f=$(printf "$d/f%06d.jpg" $n); if [ -e "$f" ]; then prev=$f; elif [ -n "$prev" ]; then ln "$prev" "$f"; fi; done; done
