# VGGT-on-Modal feasibility spike — REPORT

**Verdict: works.** Phone video -> 40 frames -> VGGT-1B on a Modal A10G -> camera poses + depth + point map + confidences -> local 2D occupancy grid, in ~90 s wall clock per run (cold) and under 10 min total spike setup. Total spike wall clock (incl. image build, one failed A100 attempt, grid code): ~8 min.

## What worked
- `pip install git+https://github.com/facebookresearch/vggt` inside `modal.Image.debian_slim(python_version="3.11")` with torch 2.4.1 built on the **first attempt** (image build 67 s, cached afterwards).
- `VGGT.from_pretrained("facebook/VGGT-1B")` downloads from the public HF repo **without a token** (confirmed: Modal logged "sending unauthenticated requests to the HF Hub" and succeeded). Weights are cached in Modal Volume `vggt-hf-cache` (HF_HOME) so later cold starts skip the ~5 GB download.
- 40 frames at 1024x683 -> VGGT resizes to 518x350 -> full aggregator + camera head + depth head + point head.
- Returned to local as one compressed `.npz` (180 MB): `extrinsic (40,3,4)` world->cam OpenCV, `intrinsic (40,3,3)`, `depth (40,350,518)`, `depth_conf`, `world_points (40,350,518,3)` (point head), `world_points_conf`, `world_points_from_depth` (unprojected depth, recommended by VGGT README), `images`, `timings`.
- Local `make_grid.py` produced the occupancy grid PNG + JSON, top-down height-coloured scatter, and grid+trajectory overlay.

## What did not work / caveats
- **A100 is blocked on this Modal account** ("Please add a payment method to use A100-40GB"). A10G (24 GB) worked and is plenty: peak VRAM **9.39 GB** for 40 frames. `VGGT_GPU=A100-40GB modal run ...` once billing is added, or keep A10G.
- Local `ffmpeg` was broken at spike start (missing libx265 dylib); frames were extracted with OpenCV (`extract_frames.py`). ffmpeg has since been reinstalled (9.0.1) and the ffmpeg command below was verified to produce equivalent 40 frames @ 1024x682.
- **The test video (hoohoo.mov) is a static selfie / talking-head, not a room walkthrough.** Consequences (all expected, none are pipeline bugs):
  - Camera centres move by millimetres -> essentially no parallax -> depth/point confidences are uniformly low (depth_conf max 1.50, median 1.00; VGGT conf >= 1). The percentile confidence filter keeps the top half rather than an absolute threshold for this reason.
  - Floor is not visible, so RANSAC ground plane disagrees with camera-up by 54 deg and the script falls back to the camera-up axis; the "1.4 m camera height" normalisation is then meaningless (raw cam height 0.197 -> scale x7.1). Grid geometry is therefore not metric for this clip. The occupied blob at the origin is the person; far fragments are wall/door.
  - Depth maps themselves look good (see `out/depth_frame0.png`: person cleanly segmented from background).
  - With a real walkthrough (camera translating ~1.4 m above a visible floor), the same script should yield a usable metric-ish grid; the ground-plane + camera-height logic is untested on real data and is the first thing to validate next.
- VGGT scale is arbitrary. Normalising by assumed camera height (1.4 m) is the plan; alternatives: known door width, or ARKit/phone IMU scale if we later capture with an app.
- 40 frames is safe; VGGT README benchmark shows ~200 frames fit in 40 GB, so on A10G ~80-100 frames should be OK (untested).

## Timings (run 2, A10G, first cold start with weight download)
| Stage | Time |
|---|---|
| Image build (one-off, cached) | 67 s |
| Container cold start + model load (incl. ~5 GB HF download, now cached in Volume) | 44.3 s |
| Frame upload (3.2 MB, 40 frames) | < 1 s |
| **GPU inference, 40 frames @ 518x350** | **5.94 s** |
| Remote fn total (preprocess + inference + pack npz) | 7.3 s |
| `modal run` wall clock end-to-end (cold) | 88.9 s |
| Download of results (180 MB npz) | included above |
| Local grid build (`make_grid.py`) | ~15 s |
| Peak VRAM | 9.39 GB (A10G 24 GB) |

Warm starts should be ~15-25 s wall (no download, model load from Volume). Adding `min_containers=1` or `scaledown_window` keeps it hot for a demo.

## Files
- `extract_frames.py` — OpenCV frame extractor (fallback when ffmpeg is unavailable)
- `vggt_modal.py` — Modal app (image, `VGGTRunner` class, local entrypoint)
- `make_grid.py` — local: confidence filter, ground plane, scale normalisation, occupancy grid, plots
- `frames/` — 40 extracted frames
- `out/vggt_out.npz` — raw VGGT output
- `out/occupancy_grid.png`, `out/occupancy_grid.json` — grid (0 unknown / 1 free / 2 occupied; 0.1 m cells; origin + trajectory + scale factor in JSON)
- `out/topdown_scatter.png` — point cloud top-down coloured by height, with camera path
- `out/grid_with_trajectory.png` — grid with camera trajectory overlay
- `out/depth_frame0.png` — RGB | depth sanity preview
- `out/modal_run1.log` (A100 refused), `out/modal_run2.log` (A10G success)

## Exact commands to rerun on a new video
```bash
cd /Users/sissi/weavehacks/spikes/vggt_modal
MODAL=/Library/Frameworks/Python.framework/Versions/3.12/bin/modal
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
VIDEO=/path/to/walkthrough.mov
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")

# 1. ~40 evenly spaced frames, 1024 px wide (VGGT resizes to 518 long edge itself)
rm -rf frames && mkdir frames
ffmpeg -hide_banner -loglevel error -y -i "$VIDEO" -vf "fps=40/$DUR,scale=1024:-2" -q:v 2 frames/frame_%03d.jpg
#    (or, without ffmpeg:)  $PY extract_frames.py "$VIDEO" frames 40 1024

# 2. VGGT on Modal (A10G default; VGGT_GPU=A100-40GB once billing is enabled)
$MODAL run vggt_modal.py --frames-dir frames --out out/vggt_out.npz --max-frames 40

# 3. Occupancy grid + plots
$PY make_grid.py out/vggt_out.npz out/
```
Requires local: numpy, opencv-python, matplotlib (all present in the 3.12 Framework python). Modal profile `sissiwang` already authenticated.

## Recommended next steps for the real pipeline
1. Re-run on an actual walkthrough video to validate ground-plane + camera-height scale (the untested part).
2. Convert `VGGTRunner` to a persistent deployed app (`modal deploy`) with `scaledown_window=300` so demo latency is ~10 s instead of ~90 s.
3. Return only what the grid needs (depth + conf + extrinsics + intrinsics, float16) to cut the 180 MB payload to ~30 MB; or write to a Modal Volume and run `make_grid.py` remotely too.
4. Consider `world_points_from_depth` (used here) vs. point-head output; VGGT README says the depth-based one is usually more accurate.
