"""B-roll: a Unitree Go2 (Genesis sim) dropped into the scanned map as a heightfield, rendered headless to MP4.

Run with the Genesis venv:  spikes/genesis_sim/.venv/bin/python cogmap/broll_genesis.py out/lux/scan/belief_v0.json out/lux/go2_on_map.mp4
"""
import json
import os
import sys
import time

import numpy as np


def main(belief_path: str, out: str, backend: str = "cpu", n_steps: int = 500):
    import genesis as gs
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    b = json.load(open(belief_path))
    grid = np.array(b["grid"], dtype=np.uint8)
    # crop to known region
    ys, xs = np.where(grid != 0)
    r0, r1, c0, c1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    g = grid[r0:r1, c0:c1]
    HS, VS = 0.15, 0.01
    h = np.where(g == 2, 0.45, 0.0)                       # occupied -> 45 cm blocks; free/unknown -> floor
    h[g == 0] = 0.08                                      # unknown -> slightly raised (visual hint)
    hf = np.round(h / VS).astype(np.int32)
    gs.init(backend=getattr(gs, backend), logging_level="warning")
    scene = gs.Scene(sim_options=gs.options.SimOptions(dt=0.01, substeps=2),
                     vis_options=gs.options.VisOptions(shadow=True, show_world_frame=False), show_viewer=False)
    scene.add_entity(gs.morphs.Terrain(horizontal_scale=HS, vertical_scale=VS, height_field=hf, pos=(0, 0, 0)))
    # spawn on a free cell with the most free space around it
    from scipy import ndimage
    free = (g == 1).astype(float)
    room = ndimage.uniform_filter(free, 7)
    ri, ci = np.unravel_index(int(np.argmax(room)), room.shape)
    spawn = np.array([ri * HS, ci * HS, 0.45])
    robot = scene.add_entity(gs.morphs.URDF(file="urdf/go2/urdf/go2.urdf", pos=tuple(spawn), quat=(1, 0, 0, 0)))
    cam = scene.add_camera(res=(960, 540), pos=tuple(spawn + [2.2, -2.2, 1.4]), lookat=tuple(spawn), fov=45, GUI=False)
    t0 = time.time()
    scene.build()
    print(f"build {time.time()-t0:.1f}s, grid {g.shape}, spawn cell ({ri},{ci})")
    joint_names = [f"{leg}_{j}_joint" for leg in ("FR", "FL", "RR", "RL") for j in ("hip", "thigh", "calf")]
    dofs = [robot.get_joint(n_).dofs_idx_local[0] for n_ in joint_names]
    default_q = np.array([0.0, 0.8, -1.5] * 4)
    robot.set_dofs_kp(np.full(12, 60.0), dofs); robot.set_dofs_kv(np.full(12, 2.0), dofs)
    robot.set_dofs_position(default_q, dofs)
    cam.start_recording(save_to_filename=out, fps=50)
    N_STAND = 100
    for i in range(N_STAND + n_steps):
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
        ang = 0.004 * i
        cam.set_pose(pos=p + np.array([2.6 * np.cos(ang), 2.6 * np.sin(ang), 1.5]), lookat=p + np.array([0, 0, 0.1]))
    cam.stop_recording()
    print("wrote", out, f"in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "cpu")
