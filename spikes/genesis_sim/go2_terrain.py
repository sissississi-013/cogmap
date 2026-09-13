"""Go2 on a custom heightfield terrain (numpy array), headless render to MP4.
Usage: python go2_terrain.py [metal|cpu] [out.mp4]"""
import sys, time, os, resource
import numpy as np
import genesis as gs

backend = sys.argv[1] if len(sys.argv) > 1 else "metal"
out = sys.argv[2] if len(sys.argv) > 2 else "out/go2_terrain.mp4"
os.makedirs(os.path.dirname(out), exist_ok=True)

t0 = time.time()
gs.init(backend=getattr(gs, backend), logging_level="warning")

# --- heightfield: 40x40 cells @ 0.25 m = 10 m x 10 m; heights in units of vertical_scale ---
HS, VS = 0.25, 0.01
n = 40
xs, ys = np.meshgrid(np.arange(n) * HS, np.arange(n) * HS, indexing="ij")
h = 0.12 * np.sin(xs * 1.2) * np.cos(ys * 0.9)          # rolling hills (m)
h += 0.10 * ((xs > 6.5) & (xs < 7.5)).astype(float)     # a 10 cm step/ledge
rng = np.random.default_rng(0)
h += 0.02 * rng.random((n, n))                           # pebbly noise
h -= h.min()
hf = np.round(h / VS).astype(np.int32)                   # integer height units
np.save("out/heightfield.npy", hf)

scene = gs.Scene(
    sim_options=gs.options.SimOptions(dt=0.01, substeps=2),
    vis_options=gs.options.VisOptions(shadow=True, show_world_frame=False),
    show_viewer=False,
)
terrain = scene.add_entity(
    gs.morphs.Terrain(horizontal_scale=HS, vertical_scale=VS, height_field=hf, pos=(0, 0, 0))
)
# spawn at grid center, above local terrain height
ci = n // 2
spawn = np.array([ci * HS, ci * HS, hf[ci, ci] * VS + 0.45])
robot = scene.add_entity(gs.morphs.URDF(file="urdf/go2/urdf/go2.urdf", pos=tuple(spawn), quat=(1, 0, 0, 0)))
cam = scene.add_camera(res=(960, 540), pos=tuple(spawn + [1.6, -1.6, 0.6]), lookat=tuple(spawn + [0.2, 0, -0.3]), fov=40, GUI=False)
scene.build()
t_build = time.time() - t0

joint_names = [f"{leg}_{j}_joint" for leg in ("FR", "FL", "RR", "RL") for j in ("hip", "thigh", "calf")]
dofs = [robot.get_joint(n_).dofs_idx_local[0] for n_ in joint_names]
default_q = np.array([0.0, 0.8, -1.5] * 4)
robot.set_dofs_kp(np.full(12, 60.0), dofs)
robot.set_dofs_kv(np.full(12, 2.0), dofs)
robot.set_dofs_position(default_q, dofs)

N_STAND, N_TROT = 100, 400
cam.start_recording(save_to_filename=out, fps=50)
t1 = time.time()
for i in range(N_STAND + N_TROT):
    q = default_q.copy()
    if i >= N_STAND:
        ph = 2 * np.pi * 2.0 * (i - N_STAND) * 0.01
        for k, leg in enumerate(("FR", "FL", "RR", "RL")):
            s = np.sin(ph + (0 if leg in ("FR", "RL") else np.pi))
            lift = max(s, 0.0)
            q[3 * k + 1] += 0.20 * lift
            q[3 * k + 2] -= 0.35 * lift
    robot.control_dofs_position(q, dofs)
    scene.step()
    p = np.asarray(robot.get_pos().cpu())
    if i % 100 == 0:
        print(f"step {i}: base pos = {np.round(p, 3)}")
    cam.set_pose(pos=p + np.array([1.6, -1.6, 0.7]), lookat=p + np.array([0.2, 0, -0.1]))
t_sim = time.time() - t1
cam.stop_recording()

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
print(f"backend={backend} build={t_build:.1f}s sim+render {N_STAND+N_TROT} steps={t_sim:.1f}s "
      f"({(N_STAND+N_TROT)/t_sim:.1f} steps/s) maxRSS={rss:.2f} GB -> {out}")
