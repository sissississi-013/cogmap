#!/usr/bin/env bash
# Assemble a silent B-roll reel from a run: scan overview -> point cloud spin (skipped) -> swarm animation -> curve -> Go2.  Usage: scripts/make_reel.sh out/office
set -euo pipefail
RUN="${1:?run dir}"; OUT="$RUN/reel.mp4"; T=$(mktemp -d)
FF=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg; [ -x "$FF" ] || FF=ffmpeg
still() { "$FF" -v error -y -loop 1 -t "$2" -i "$1" -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=#111111,format=yuv420p" -r 30 "$3"; }
still "$RUN/scan/scan_overview.png" 5 "$T/a.mp4"
"$FF" -v error -y -i "$RUN/swarm.mp4" -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=#111111,format=yuv420p" -r 30 "$T/b.mp4"
still "$RUN/curve.png" 5 "$T/c.mp4"
still "$RUN/steps_to_recover.png" 4 "$T/d.mp4"
GO2=$(ls "$RUN"/go2_walk.mp4 "$RUN"/go2_on_map.mp4 2>/dev/null | head -1 || true)
LIST="$T/list.txt"; for f in a b c d; do echo "file '$T/$f.mp4'" >> "$LIST"; done
if [ -n "$GO2" ]; then "$FF" -v error -y -i "$GO2" -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=#111111,format=yuv420p" -r 30 "$T/e.mp4"; echo "file '$T/e.mp4'" >> "$LIST"; fi
"$FF" -v error -y -f concat -safe 0 -i "$LIST" -c:v libx264 -crf 20 -pix_fmt yuv420p "$OUT"
echo "reel: $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")s)"; rm -rf "$T"
