"""Go2 on a flat plane, headless render to MP4. Usage: python go2_flat.py [metal|cpu] [out.mp4]"""
import sys, time, os, resource
import numpy as np
import genesis as gs

backend = sys.argv[1] if len(sys.argv) > 1 else "metal"
out = sys.argv[2] if len(sys.argv) > 2 else "out/go2_flat.mp4"
os.makedirs(os.path.dirname(out), exist_ok=True)

t0 = time.time()
gs.init(backend=getattr(gs, backend), logging_level="warning")

scene = gs.Scene(
    sim_options=gs.options.SimOptions(dt=0.01, substeps=2),
    vis_options=gs.options.VisOptions(shadow=True, show_world_frame=False),
    show_viewer=False,
)
plane = scene.add_entity(gs.morphs.Plane())
robot = scene.add_entity(
    gs.morphs.URDF(file="urdf/go2/urdf/go2.urdf", pos=(0, 0, 0.45), quat=(1, 0, 0, 0))
)
cam = scene.add_camera(res=(960, 540), pos=(1.6, -1.6, 0.9), lookat=(0.2, 0, 0.25), fov=40, GUI=False)
scene.build()
t_build = time.time() - t0

# --- standing pose + PD gains (from Genesis go2 locomotion example) ---
joint_names = [f"{leg}_{j}_joint" for leg in ("FR", "FL", "RR", "RL") for j in ("hip", "thigh", "calf")]
dofs = [robot.get_joint(n).dofs_idx_local[0] for n in joint_names]
default_q = np.array([0.0, 0.8, -1.5] * 4)
robot.set_dofs_kp(np.full(12, 60.0), dofs)
robot.set_dofs_kv(np.full(12, 2.0), dofs)
robot.set_dofs_position(default_q, dofs)

N_STAND, N_TROT = 100, 400
cam.start_recording(save_to_filename=out, fps=50)
t1 = time.time()
for i in range(N_STAND + N_TROT):
    q = default_q.copy()
    if i >= N_STAND:  # crude open-loop trot: diagonal pairs swing in antiphase
        ph = 2 * np.pi * 2.0 * (i - N_STAND) * 0.01  # 2 Hz
        for k, leg in enumerate(("FR", "FL", "RR", "RL")):
            s = np.sin(ph + (0 if leg in ("FR", "RL") else np.pi))
            lift = max(s, 0.0)
            q[3 * k + 1] += 0.20 * lift  # thigh: lift on swing
            q[3 * k + 2] -= 0.35 * lift  # calf: fold on swing
    robot.control_dofs_position(q, dofs)
    scene.step()
    if i % 100 == 0:
        p = robot.get_pos()
        print(f"step {i}: base pos = {np.round(np.asarray(p.cpu() if hasattr(p, 'cpu') else p), 3)}")
    # follow the robot
    p = np.asarray(robot.get_pos().cpu())
    cam.set_pose(pos=p + np.array([1.6, -1.6, 0.7]), lookat=p + np.array([0.2, 0, -0.1]))
t_sim = time.time() - t1
cam.stop_recording()

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
print(f"backend={backend} build={t_build:.1f}s sim+render {N_STAND+N_TROT} steps={t_sim:.1f}s "
      f"({(N_STAND+N_TROT)/t_sim:.1f} steps/s) maxRSS={rss:.2f} GB -> {out}")
