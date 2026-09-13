# Research (deep): robot-nav loop — real-robot grounding, loop refs, object anchoring, viz, framing

(Research agent report, 2026-09-13 ~03:45 PDT)

## 1. Real-robot grounding (Go2/G1)
- Go2 Pro/EDU ships 4D LiDAR; Unitree app builds point-cloud map + path points (https://support.unitree.com/home/en/developer/SLAM%20and%20Navigation_service). Developer `unitree_slam` (SDK2/CycloneDDS) keeps a *topological node/edge map* (add_node/add_edge/delete_node/query_node; https://github.com/unitreerobotics/unitree_slam). No public doc shows loading an external map into Unitree's service. G1 has no built-in nav stack.
- **Honest transfer path = ROS2 Nav2.** Real Go2 deployments run slam_toolbox/RTAB-Map + Nav2 and consume `nav2_map_server` pair: `map.pgm` (or .png) + `map.yaml` {image, resolution, origin [x,y,yaw], negate, occupied_thresh, free_thresh} (https://github.com/ros-planning/navigation2/blob/main/nav2_map_server/README.md). Examples: amigo_ros2, unitree_go2_nav (RTAB-Map + nav-to-pose), go2_ros2_sdk (WebRTC, Air/Pro), OpenMind/unitree-sdk (slam_toolbox + Nav2 for Go2 and G1), arXiv 2606.03340.
- Claim to make: "Our exporter writes the Nav2 map_server artifact (map.pgm + map.yaml, resolution 0.05) plus waypoints.json (named poses → nav2_simple_commander.followWaypoints). That is what a Go2/G1 running slam_toolbox+Nav2 loads today." Don't claim the Unitree app ingests it. Caveats: VGGT map is up-to-scale (fix with known object / step length); Nav2 still needs AMCL relocalization — our map is the *prior*, which is why "repair after objects move" is a real problem.
- Timeliness/skepticism: FCC put foreign mobile robots on the Covered List 2026-07-28; current Go2/G1/A2 remain sellable (IEEE Spectrum). Say "Nav2-compatible robots (Go2/G1 today)".

## 2. Loop-design references
- Frontier exploration (Yamauchi 1997): frontier = free cell adjacent to unknown; multi-robot shared-grid variants: coExplore (2303.17459), novelty-sharing (2402.02097), shared exploration maps MAPF (2503.22162).
- Scene-graph updating from observation/failure: GraphPad (2506.01174), Multi-Modal 3D SG Updater (2411.02938; LLM picks add/remove/move ops, per-op success), SG particle filtering (2411.15027), GRIP (2510.10865; LLM introspection over symbolic nav failures), ConceptGraphs, MR-COGraphs (2412.18381).
- Map as rewritable LLM memory: VLMaps, MapGPT, MC-GPT (2405.10620), CMMR-VLN (2603.07997; store successful paths + first mistake of failures), SayNav (2309.04077). Reflexion generic.
- **Simplest loop that visibly improves in 3–5 iterations:**
  1. Belief grid B (free/occupied/unknown + per-cell confidence) + object table {name, cell, conf}.
  2. N agents plan A* on B, execute on TRUE grid; each step compares expected vs observed (3×3 sensor from true grid or re-detected keyframe). Mismatches → failure_events (cell, expected, observed, agent, t).
  3. Repair op (rule-based first, LLM second): cells with ≥k conflicting observations flip; objects with moved centroid → relocate; unknown frontiers get exploration bonus. LLM proposes ops over scene-graph JSON given the failure log (GraphPad-style), validated against geometry before commit.
  4. Bump map_version, re-run fixed eval set (fixed start/goal pairs), log success/SPL/collisions to Weave. Perturb again on iteration 3 to show re-heal. Curve "v1 90% → move couch → 40% → v2 85% → v3 92%" is the demo.

## 3. Objects → grid cells
Per keyframe: detector box → median of inner 30% of box pixels → VGGT per-pixel point map (no intrinsics math) → world via VGGT pose → drop z → cell = ((x-ox)/res, (y-oy)/res). Cluster per label across frames (DBSCAN eps≈0.4m) → one node per object; mark footprint occupied. Height filter (floor ±2m), reject boxes >60% frame.
Detectors on Mac arm64 CPU: OWLv2 via transformers (`google/owlv2-base-patch16-ensemble`, 1–3 s/frame CPU) — recommended with 10-word vocab. YOLO-World/YOLOE via ultralytics faster but pulls CLIP from GitHub on first set_classes. Claude vision boxes for labeling only, not localization.

## 4. Visualization (<1h)
- 3D: `pip install rerun-sdk`; rr.Points3D + rr.Pinhole/Transform3D; rr.save("scan.rrd"); screen-record viewer. Plotly Scatter3d HTML = 10-min fallback.
- 2D agents: matplotlib FuncAnimation + imshow grid + scatter agents → ani.save("run.mp4", writer="ffmpeg"). Belief grid left / true grid right, failure events as red X.
- Weave: weave.Evaluation with fixed dataset of (start, goal) + `success` scorer; run once per map_version naming model map_v{n}; Evaluations → Compare, or Leaderboard (https://docs.wandb.ai/weave/guides/evaluation/dynamic_leaderboards). EvaluationLogger for imperative loop. @weave.op on repair LLM call so judges see failures → proposed ops → validated ops.

## 5. "World model as digital asset" framing
Niantic Spatial launched Scaniverse + VPS 2.0 (Apr 2026) as "mapping the world for machines", sold to robotics OEMs (https://www.nianticspatial.com/robotics). Apple RoomPlan; Matterport/HM3D, ReplicaCAD, HSSD, ProcTHOR as sim-scene lineage. Pitch: "Scaniverse makes the phone scan; we make it learnable and self-repairing and export the artifact a Nav2 robot actually loads." Unitree targeting Q3–Q4 2026 home G1 shipments ($20k / $499-mo). Phrase: "the map outlives the robot generation."

## 3-minute demo script
0:00–0:25 phone walkthrough; rerun point cloud + frustums ("this is the world model").
0:25–0:50 grid + object nodes (couch/chair/door); export map.pgm/.yaml on screen.
0:50–1:20 8 agents navigate; Weave eval v1: 90%.
1:20–1:45 "someone moved the couch": true grid changes, agents collide, success ~40%; failure log scrolls.
1:45–2:20 repair op trace in Weave (failures → LLM ops → validated → v2), success climbs v2/v3; leaderboard.
2:20–2:45 Genesis Go2 B-roll / Nav2 RViz screenshot loading the same .pgm.
2:45–3:00 asset framing + ecosystem slide.

## Build order (~7h, hard cutoffs)
1. H0–1 grid world + A* + N agents + fixed eval set + Weave Evaluation. Cutoff 1:15.
2. H1–2.5 failure detection + rule-based repair + perturbation → success curve. Cutoff 2:30: loop must show recovery WITHOUT the LLM.
3. H2.5–3.5 LLM repair op over scene-graph JSON, @weave.op, validation gate. Cutoff 3:30.
4. H3.5–5 real scan: VGGT poses/points → occupancy grid → OWLv2 objects → cells; export .pgm/.yaml/waypoints.json. Cutoff 5:00: fall back to hand-drawn grid of same room.
5. H5–6 matplotlib MP4, rerun recording, Nav2 map_server load screenshot (docker ros:humble + nav2_map_server).
6. H6–7 demo cut, README, leaderboard screenshots. Freeze 6:30.
