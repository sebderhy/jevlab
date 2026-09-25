#!/bin/bash
# Three-track "latency removed" video: Jev | DeepSeek | Kev-4B from ~/tmp/final/slowed-{jev,llm,kev}, 2x playback, caption strip.
# Captions from ~/tmp/final/cap-slowed/{t,1a,1b,2a,2b,3a,3b}.txt. Kev's frames were captured before render.js named open models
# (their title reads "kev · LOCAL FALLBACK"): the drawbox repaints that one title. Usage: final-compose.sh out.mp4
cd /home/seb/tmp/final
F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; B=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
dt() { echo "drawtext=fontfile=$1:textfile=cap-slowed/$2:x=$3:y=$4:fontsize=$5:fontcolor=$6"; }
FILTER="[0:v][1:v][2:v]hstack=3,pad=iw:ih+118:0:118:color=0x14181c,$(dt $F t.txt 14 12 20 0xb8c0cc),drawtext=fontfile=$F:text='sim %{eif\:2*t\:d} s':x=w-tw-16:y=12:fontsize=20:fontcolor=0xb8c0cc,$(dt $B 1a.txt 14 54 22 0xff6fa8),$(dt $F 1b.txt 14 86 14 0xd0d6de),$(dt $B 2a.txt 614 54 22 0x79b8ff),$(dt $F 2b.txt 614 86 14 0xd0d6de),$(dt $B 3a.txt 1214 54 22 0x5fd35f),$(dt $F 3b.txt 1214 86 14 0xd0d6de),drawbox=x=1500:y=132:w=296:h=22:color=0x14181c@1:t=fill,drawtext=fontfile=$B:text='OPEN MODEL · kev-4b (CPU)':x=1786-tw:y=137:fontsize=13:fontcolor=0x5fd35f"
ffmpeg -y -loglevel error -framerate 60 -i slowed-jev/f%06d.jpg -framerate 60 -i slowed-llm/f%06d.jpg -framerate 60 -i slowed-kev/f%06d.jpg -filter_complex "$FILTER" -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -movflags +faststart "$1"
