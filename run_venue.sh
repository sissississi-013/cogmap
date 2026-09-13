#!/usr/bin/env bash
# One-shot morning script: phone clip -> CogMap loop -> visuals -> Go2 B-roll.  Usage: ./run_venue.sh footage/raw/venue.mov [out/venue]
set -euo pipefail
VIDEO="${1:?usage: ./run_venue.sh <video> [out_dir]}"; OUT="${2:-out/venue}"
cd "$(dirname "$0")"
source .venv/bin/activate
set -a; source .env; set +a
mkdir -p "$OUT"
echo "== CogMap on $VIDEO -> $OUT  ($(date +%H:%M:%S))"
python -u run_demo.py --video "$VIDEO" --out "$OUT" --n-tasks 12 2>&1 | tee "$OUT/log.txt" | grep --line-buffered -E "^\[scan\]|^\[eval\]|=== Round|round .* done|patrol detected|repair #|leaderboard|Traceback|weave images"
if [ -x spikes/genesis_sim/.venv/bin/python ]; then
  echo "== Go2 B-roll (walks an A* path on the scanned map)"
  spikes/genesis_sim/.venv/bin/python -u cogmap/broll_genesis.py walk "$OUT/scan/belief_v0.json" "$OUT/scan/world.json" "$OUT/scan/tasks.json" "$OUT/go2_walk.mp4" cpu 2>&1 | grep -E "wrote|Error" || true
fi
scripts/make_reel.sh "$OUT" || true
echo "== done ($(date +%H:%M:%S)). Open: $OUT/scan/scan_overview.png  $OUT/curve.png  $OUT/swarm.mp4  $OUT/scan/pointcloud.html  ->  marimo run dashboard.py"
