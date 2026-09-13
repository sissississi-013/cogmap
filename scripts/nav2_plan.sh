#!/usr/bin/env bash
# Prove a stock ROS 2 Nav2 planner (NavFn) plans on the exported CogMap map.  Usage: scripts/nav2_plan.sh out/office
# Builds a cached image (scripts/Dockerfile.nav2, pulled from the AWS public mirror), loads map.yaml in map_server,
# brings up planner_server + static global costmap, and calls /compute_path_to_pose from task t0's start to its goal waypoint.
set -euo pipefail
RUN="$(cd "${1:?run dir}" && pwd)"; HERE="$(cd "$(dirname "$0")" && pwd)"; TMP="$(mktemp -d)"
python3 - "$RUN" "$HERE/nav2_plan_inner.sh" "$TMP/plan.sh" <<'PY'
import json, sys
run, src, dst = sys.argv[1:]
wp = json.load(open(f"{run}/scan/nav2/waypoints.json"))["waypoints"]; tasks = json.load(open(f"{run}/scan/tasks.json"))
meta = json.load(open(f"{run}/scan/grid_meta.json")); res, lo = meta["cell"], meta["origin_xy"]
t = tasks[0]; s = t["start"]; g = wp[t["goal"]]
sx, sy = lo[0] + (s[1] + 0.5) * res, lo[1] + (s[0] + 0.5) * res
open(dst, "w").write(open(src).read().replace("START_X", f"{sx:.3f}").replace("START_Y", f"{sy:.3f}").replace("GOAL_X", f"{g['x']:.3f}").replace("GOAL_Y", f"{g['y']:.3f}").replace("GOAL_NAME", t["goal"]))
print(f"start ({sx:.2f},{sy:.2f}) -> {t['goal']} ({g['x']},{g['y']})")
PY
docker build -q -t cogmap-nav2 -f "$HERE/Dockerfile.nav2" "$HERE" >/dev/null
mkdir -p "$RUN/nav2_proof"
docker run --rm -v "$RUN/scan/nav2:/maps:ro" -v "$RUN/nav2_proof:/out" -v "$TMP/plan.sh:/plan.sh:ro" cogmap-nav2 bash /plan.sh | tee "$RUN/nav2_proof/planner.log"
rm -rf "$TMP"
