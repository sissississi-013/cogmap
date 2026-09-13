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
    h = np.where(g == 2, 0.30, 0.0)                       # occupied -> 30 cm blocks (furniture footprints); free/unknown -> floor
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
    cam = scene.add_camera(res=(960, 540), pos=tuple(spawn + [2.2, -2.2, 1.4]), lookat=tuple(spawn), fov=50, GUI=False)
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
        ang = 0.003 * i
        cam.set_pose(pos=p + np.array([3.0 * np.cos(ang), 3.0 * np.sin(ang), 2.0]), lookat=p + np.array([0, 0, 0.1]))
    cam.stop_recording()
    print("wrote", out, f"in {time.time()-t0:.1f}s")


if __name__ == "__main__" and sys.argv[1] != "walk":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "cpu")


def walk_path(belief_path: str, world_path: str, tasks_path: str, out: str, backend: str = "cpu", steps_per_cell: int = 12):
    """Go2 walks an A* path from the CogMap belief (base moved kinematically along the path while the legs trot)."""
    import genesis as gs
    from scipy import ndimage
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    b = json.load(open(belief_path)); grid = np.array(b["grid"], dtype=np.uint8)
    tasks = json.load(open(tasks_path))
    # A* on known-free cells (import lazily to keep this file runnable from the Genesis venv without weave)
    import heapq
    H, W = grid.shape
    objs = b["objects"]
    def astar(start, goals):
        def h(c): return min(abs(c[0]-g[0])+abs(c[1]-g[1]) for g in goals)
        openq=[(h(start),0,start)]; came={}; gsc={start:0}; seen=set()
        while openq:
            _,g,cur=heapq.heappop(openq)
            if cur in seen: continue
            seen.add(cur)
            if cur in goals:
                p=[cur]
                while cur in came: cur=came[cur]; p.append(cur)
                return p[::-1]
            for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)):
                nb=(cur[0]+dr,cur[1]+dc)
                if 0<=nb[0]<H and 0<=nb[1]<W and grid[nb]==1 and nb not in seen and g+1<gsc.get(nb,1e9):
                    gsc[nb]=g+1; came[nb]=cur; heapq.heappush(openq,(g+1+h(nb),g+1,nb))
        return None
    path = None
    for t in tasks:
        cells = {tuple(c) for c in objs[t["goal"]]["cells"]}
        goals = set()
        for (r,c) in cells:
            for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)):
                nb=(r+dr,c+dc)
                if 0<=nb[0]<H and 0<=nb[1]<W and grid[nb]==1 and nb not in cells: goals.add(nb)
        p = astar(tuple(t["start"]), goals) if goals else None
        if p and len(p) > 20:
            path = p; goal_name = t["goal"]; break
    if path is None:
        raise SystemExit("no long enough path")
    ys, xs = np.where(grid != 0)
    r0, c0 = ys.min(), xs.min()
    g = grid[ys.min():ys.max()+1, xs.min():xs.max()+1]
    HS, VS = 0.15, 0.01
    hf = np.round(np.where(g == 2, 0.30, 0.0) / VS).astype(np.int32)
    gs.init(backend=getattr(gs, backend), logging_level="warning")
    scene = gs.Scene(sim_options=gs.options.SimOptions(dt=0.01, substeps=2),
                     vis_options=gs.options.VisOptions(shadow=True, show_world_frame=False), show_viewer=False)
    scene.add_entity(gs.morphs.Terrain(horizontal_scale=HS, vertical_scale=VS, height_field=hf, pos=(0, 0, 0)))
    def xyz(cell):  # grid (row, col) -> terrain (x=row*HS, y=col*HS)
        return np.array([(cell[0]-r0)*HS, (cell[1]-c0)*HS, 0.32])
    start = xyz(path[0])
    robot = scene.add_entity(gs.morphs.URDF(file="urdf/go2/urdf/go2.urdf", pos=tuple(start), quat=(1, 0, 0, 0)))
    cam = scene.add_camera(res=(960, 540), pos=tuple(start + [2.5, -2.5, 2.0]), lookat=tuple(start), fov=50, GUI=False)
    scene.build()
    joint_names = [f"{leg}_{j}_joint" for leg in ("FR", "FL", "RR", "RL") for j in ("hip", "thigh", "calf")]
    dofs = [robot.get_joint(n_).dofs_idx_local[0] for n_ in joint_names]
    default_q = np.array([0.0, 0.8, -1.5] * 4)
    robot.set_dofs_kp(np.full(12, 80.0), dofs); robot.set_dofs_kv(np.full(12, 3.0), dofs)
    robot.set_dofs_position(default_q, dofs)
    pts = np.array([xyz(c) for c in path])
    cam.start_recording(save_to_filename=out, fps=50)
    n_total = steps_per_cell * (len(pts) - 1)
    for i in range(n_total):
        seg, f = divmod(i, steps_per_cell)
        p = pts[seg] + (pts[seg + 1] - pts[seg]) * (f / steps_per_cell)
        d = pts[min(seg + 1, len(pts) - 1)] - pts[seg]
        yaw = float(np.arctan2(d[1], d[0])) if np.linalg.norm(d[:2]) > 1e-6 else 0.0
        quat = (float(np.cos(yaw / 2)), 0.0, 0.0, float(np.sin(yaw / 2)))
        robot.set_pos(p, zero_velocity=True); robot.set_quat(np.array(quat), zero_velocity=True)
        q = default_q.copy(); ph = 2 * np.pi * 2.5 * i * 0.01
        for k, leg in enumerate(("FR", "FL", "RR", "RL")):
            s_ = np.sin(ph + (0 if leg in ("FR", "RL") else np.pi)); lift = max(s_, 0.0)
            q[3 * k + 1] += 0.25 * lift; q[3 * k + 2] -= 0.40 * lift
        robot.control_dofs_position(q, dofs)
        scene.step()
        ang = -0.6 + 0.0015 * i
        cam.set_pose(pos=p + np.array([2.4 * np.cos(ang), 2.4 * np.sin(ang), 1.6]), lookat=p + np.array([0, 0, 0.1]))
    cam.stop_recording()
    print(f"wrote {out}: Go2 walked {len(path)} cells to {goal_name}")


if __name__ == "__main__" and len(sys.argv) > 4 and sys.argv[1] == "walk":
    walk_path(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else "cpu")
