#!/bin/bash
# Compose the three captured traffic tracks (~/tmp/av-decider/{jev,llm-real,decider}) into the Jev vs DeepSeek vs Decider video.
# Captions are read from ~/tmp/av-decider/cap/{t,1a,1b,2a,2b,3a,3b}.txt. Usage: av-decider-compose.sh out.mp4
cd /home/seb/tmp/av-decider
F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; B=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
dt() { echo "drawtext=fontfile=$1:textfile=cap/$2:x=$3:y=$4:fontsize=$5:fontcolor=$6"; }
ffmpeg -y -loglevel error -framerate 60 -i jev/f%06d.jpg -framerate 60 -i llm-real/f%06d.jpg -framerate 60 -i decider/f%06d.jpg \
 -filter_complex "[0:v][1:v][2:v]hstack=3,pad=iw:ih+118:0:118:color=0x14181c,\
$(dt $F t.txt 14 12 20 0xb8c0cc),drawtext=fontfile=$F:text='sim %{eif\:2*t\:d} s':x=w-tw-16:y=12:fontsize=20:fontcolor=0xb8c0cc,\
$(dt $B 1a.txt 14 54 22 0xff6fa8),$(dt $F 1b.txt 14 86 14 0xd0d6de),\
$(dt $B 2a.txt 614 54 22 0x79b8ff),$(dt $F 2b.txt 614 86 14 0xd0d6de),\
$(dt $B 3a.txt 1214 54 22 0xb48cff),$(dt $F 3b.txt 1214 86 14 0xd0d6de)" \
 -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -movflags +faststart "$1"
