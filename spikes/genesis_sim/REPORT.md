# Genesis Go2 spike — feasibility report

**Verdict: YES.** Genesis 1.4.1 installs, simulates the bundled Unitree Go2, and renders headless to MP4 on this
Apple Silicon Mac (M2, 16 GB, macOS Darwin 25.2) with both the Metal and CPU backends. Flat plane and custom
numpy heightfield both work. Total wall time for the spike: ~12 min (well inside the 45 min box). MuJoCo fallback
was not needed.

## Outputs

| File | What | Length |
|---|---|---|
| `out/go2_flat_metal.mp4` | Go2 drops onto plane, PD-holds a stand, then open-loop trot (walks ~0.2 m/s), Metal backend | 5 s, 960x540, 50 fps |
| `out/go2_flat_cpu.mp4` | Same scene, CPU backend (identical result) | 5 s |
| `out/go2_terrain_metal.mp4` | Go2 on a 10x10 m heightfield built from a numpy array (rolling hills + 10 cm ledge + noise) | 5 s |
| `out/heightfield.npy` | The 40x40 int32 heightfield used | |
| `out/frames/*_tile.png` | Frame grabs for sanity check | |

Scripts: `go2_flat.py`, `go2_terrain.py` (both take `[metal|cpu] [out.mp4]`).

## Exact commands

```bash
cd /Users/sissi/weavehacks/spikes/genesis_sim
uv venv .venv --python 3.12 && source .venv/bin/activate
uv pip install genesis-world        # 47 s; pulls quadrants (taichi fork), pyrender/pyopengl, moviepy, imageio-ffmpeg
uv pip install torch                # REQUIRED — genesis imports torch and is not a declared dep (86 s, torch 2.14.0)
python go2_flat.py metal out/go2_flat_metal.mp4
python go2_terrain.py metal out/go2_terrain_metal.mp4
python go2_flat.py cpu out/go2_flat_cpu.mp4
```

## Timings / memory (M2, 16 GB)

| Run | scene.build() | 500 steps + render 250 frames @960x540 | steps/s | max RSS |
|---|---|---|---|---|
| flat, metal, cold (JIT compile) | 76 s | 21 s | 24 | 0.69 GB |
| flat, metal, warm (kernel cache) | 6.6 s | 6.6 s | 76 | 0.85 GB |
| terrain, metal, cold | 49 s | 40 s | 12 | 0.99 GB |
| flat, cpu, cold | 44 s | 2.6 s | **196** | 0.82 GB |

- `gs.init()` itself is 0.2 s on both backends.
- **CPU backend is ~2.5x faster than Metal for a single robot** (Metal pays per-kernel launch overhead; GPU only wins with
  many parallel envs). For B-roll, use `gs.cpu`.
- Kernel JIT is cached on disk after the first run, so the first build of each new scene topology is 45-75 s;
  subsequent runs are ~7 s. Budget for that on demo day (pre-warm the cache).
- No GPU VRAM metric is exposed on Metal (unified memory); process RSS stayed under 1 GB throughout.

## How it works (details that matter)

- Bundled asset: `<site-packages>/genesis/assets/urdf/go2/urdf/go2.urdf` (+ `dae/` meshes). Referenced as
  `gs.morphs.URDF(file="urdf/go2/urdf/go2.urdf")` — relative paths resolve to the genesis assets dir.
  **There is no G1 humanoid in the pip package** (only `xml/humanoid.xml`, a MuJoCo-style generic humanoid, and
  `urdf/anymal_c`). Go2 is the legged robot to use.
- No locomotion policy/example is shipped in the wheel (the `examples/locomotion/go2_*.py` live only in the git repo
  and need a trained checkpoint + rsl_rl). Instead the scripts use PD position control
  (`set_dofs_kp/kv` = 60/2, `control_dofs_position`) to the standard standing pose `[hip 0, thigh 0.8, calf -1.5]x4`
  and then a crude open-loop 2 Hz diagonal-pair trot. The robot stays upright (base z = 0.30 m on flat, 0.43 m on
  terrain) and drifts ~0.2 m/s. It is not a real gait, but it reads as "robot walking" for B-roll.
- Headless rendering: `gs.Scene(show_viewer=False)` + `scene.add_camera(..., GUI=False)`. Camera in 1.4.1 records
  itself on each `scene.step()` after `cam.start_recording(save_to_filename=..., fps=50)`; `cam.stop_recording()`
  finalizes the h264 MP4. No display / Xvfb needed on macOS — the rasterizer uses an offscreen OpenGL context.
- Follow-cam: `cam.set_pose(pos=..., lookat=...)` each step.
- Heightfield: `gs.morphs.Terrain(horizontal_scale=0.25, vertical_scale=0.01, height_field=hf)` where `hf` is a 2D
  int array in units of `vertical_scale`. Terrain spans `[0, n*horizontal_scale]` in x and y from `pos`; spawn the
  robot at `(cx, cy, hf[i,j]*vertical_scale + 0.45)`. This is the hook for the "phone scan -> world model" story:
  any depth/elevation map from the scan becomes `hf`.

## Pitfalls

1. `torch` is not installed by `genesis-world`; `import genesis` raises ImportError until you `pip install torch`.
2. First-run JIT compile is long (45-75 s per scene topology) and prints scary `QuadrantsWarning` /
   "Assign may lose precision" messages — harmless.
3. Warnings you can ignore: "Neutral robot position (qpos0) exceeds joint limits" (Go2 URDF), "Mesh is not
   watertight" (terrain), and a one-time OpenGL "GLD_TEXTURE_INDEX_CUBE_MAP is unloadable" message.
4. Video length = steps * dt; with dt=0.01 and 500 steps you get 5 s. Bump `N_TROT` for longer clips
   (cost is linear, ~3-13 ms/step on CPU).
5. Aggressive open-loop gaits flip the robot (first attempt with 3 Hz, 0.35 rad swing fell over). Keep thigh lift
   <= 0.2 rad, calf fold <= 0.35 rad, 2 Hz, kp >= 60.
6. Default lighting is dim and the plane is a dark checkerboard; the terrain renders untextured white. Good enough
   for B-roll; pass `surface=gs.surfaces.Default(color=...)` or add lights via `VisOptions.lights` if you want more.
7. Rendering resolution dominates runtime on Metal; drop to 640x360 if you need faster iteration.

## Suggested next step for the demo

Use `gs.cpu`, pre-warm the kernel cache once, generate `hf` from the phone-scan depth map, spawn 1-4 Go2s at
different points, record 10-15 s at 30 fps. If real locomotion is wanted, clone the Genesis repo and use
`examples/locomotion/go2_eval.py` with its pretrained checkpoint (requires `rsl-rl-lib`, not tested here).
