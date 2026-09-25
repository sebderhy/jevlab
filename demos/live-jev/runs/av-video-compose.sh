#!/bin/bash
# Compose the four captured tracks (~/tmp/av-video/*) into the axis-split video. Usage: av-video-compose.sh out.mp4
cd /home/seb/tmp/av-video
F=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; B=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
dt() { echo "drawtext=fontfile=$1:textfile=cap/$2:x=$3:y=$4:fontsize=$5:fontcolor=$6"; }
ffmpeg -y -loglevel error -framerate 60 -i jev/f%06d.jpg -framerate 60 -i llm-real/f%06d.jpg -framerate 60 -i llm-slow/f%06d.jpg -framerate 60 -i llm-vision/f%06d.jpg \
 -filter_complex "[0:v][1:v][2:v][3:v]hstack=4,pad=iw:ih+118:0:118:color=0x14181c,\
$(dt $F t.txt 14 12 20 0xb8c0cc),drawtext=fontfile=$F:text='sim %{eif\:2*t\:d} s':x=w-tw-16:y=12:fontsize=20:fontcolor=0xb8c0cc,\
$(dt $B 1a.txt 14 54 24 0xff6fa8),$(dt $F 1b.txt 14 88 17 0xd0d6de),\
$(dt $B 2a.txt 614 54 24 0x79b8ff),$(dt $F 2b.txt 614 88 17 0xd0d6de),\
$(dt $B 3a.txt 1214 54 24 0x79b8ff),$(dt $F 3b.txt 1214 88 17 0xd0d6de),\
$(dt $B 4a.txt 1814 54 24 0x79b8ff),$(dt $F 4b.txt 1814 88 17 0xd0d6de)" \
 -c:v libx264 -preset medium -crf 22 -pix_fmt yuv420p -movflags +faststart "$1"
