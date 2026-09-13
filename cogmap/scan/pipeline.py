"""Phone video -> keyframes -> VGGT (Modal GPU) -> occupancy grid -> semantic objects -> TrueWorld/BeliefMap.

`scan_to_world(video, out_dir)` is what run_demo.py calls. Every stage is a weave.op and writes artifacts to out_dir/scan/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Dict, List, Tuple

import numpy as np
import weave
from scipy import ndimage

from ..agents import astar
from ..world import BeliefMap, TrueWorld, WorldObject, Cell, UNKNOWN, FREE, OCCUPIED, block_door, relocate_object
from .frames import extract_frames, contact_sheet
from .grid import build_grid, save_grid_png
from .objects import detect_all, anchor_objects
from .export_nav2 import export_nav2

MODAL_APP = "cogmap-vggt"


@weave.op
def run_vggt(frames: List[str], out_npz: str, max_frames: int = 48) -> dict:
    """Run VGGT-1B on Modal (deployed app; falls back to `modal run`). Returns timings."""
    t0 = time.time()
    payload = {os.path.basename(p): open(p, "rb").read() for p in frames[:max_frames]}
    data = None
    try:
        import modal
        Runner = modal.Cls.from_name(MODAL_APP, "VGGTRunner")
        data = Runner().infer.remote(payload)
    except Exception as e:  # noqa: BLE001
        print("[vggt] deployed app call failed, falling back to `modal run`:", e)
        here = os.path.join(os.path.dirname(__file__), "vggt_modal.py")
        subprocess.run([sys.executable, "-m", "modal", "run", here, "--frames-dir", os.path.dirname(frames[0]),
                        "--out", out_npz, "--max-frames", str(max_frames)], check=True)
    if data is not None:
        os.makedirs(os.path.dirname(out_npz) or ".", exist_ok=True)
        with open(out_npz, "wb") as f:
            f.write(data)
    tm = np.load(out_npz)["timings"]
    return {"n_frames": len(payload), "model_load_s": float(tm[0]), "gpu_infer_s": float(tm[1]), "peak_vram_gb": float(tm[3]),
            "wall_s": round(time.time() - t0, 1), "npz": out_npz}


def _clean_grid(grid: np.ndarray) -> np.ndarray:
    """Morphological cleanup: fill small holes in free space, drop isolated occupied specks, keep unknown."""
    g = grid.copy()
    free = g == FREE
    free = ndimage.binary_closing(free, iterations=1)
    occ = g == OCCUPIED
    lab, n = ndimage.label(occ)
    sizes = ndimage.sum(occ, lab, range(1, n + 1))
    for i, sz in enumerate(sizes, start=1):
        if sz < 2:
            occ[lab == i] = False
    g[:] = UNKNOWN
    g[free] = FREE
    g[occ] = OCCUPIED
    return g


def _largest_free_component(grid: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(grid == FREE)
    if n == 0:
        return grid == FREE
    sizes = ndimage.sum(grid == FREE, lab, range(1, n + 1))
    return lab == (int(np.argmax(sizes)) + 1)


@weave.op
def blobs_as_objects(grid: np.ndarray, existing: Dict[str, WorldObject], k: int = 6) -> Dict[str, WorldObject]:
    """Fallback landmarks: largest occupied blobs adjacent to free space become obstacle_N objects."""
    taken = np.zeros(grid.shape, bool)
    for o in existing.values():
        for c in o.cells:
            if 0 <= c[0] < grid.shape[0] and 0 <= c[1] < grid.shape[1]:
                taken[c] = True
    occ = (grid == OCCUPIED) & ~taken
    lab, n = ndimage.label(occ)
    sizes = ndimage.sum(occ, lab, range(1, n + 1))
    order = np.argsort(-sizes)
    out = dict(existing)
    free_d = ndimage.binary_dilation(grid == FREE, iterations=1)
    j = 0
    for idx in order:
        if j >= k or sizes[idx] < 3:
            break
        cells = [tuple(int(x) for x in c) for c in np.argwhere(lab == idx + 1)]
        if not any(free_d[c] for c in cells):
            continue
        cells = cells[:40]
        name = f"obstacle_{j + 1}"
        out[name] = WorldObject(name, cells, kind="obstacle", confidence=0.6)
        j += 1
    return out


def reachable_tasks(world: TrueWorld, n: int = 12, seed: int = 0, min_dist: int = 8) -> List[dict]:
    """Fixed task set on a real map: start cells in the main free component, goals reachable."""
    from ..agents import goal_cells_for
    rng = np.random.default_rng(seed)
    main = _largest_free_component(world.grid)
    free = np.argwhere(main)
    belief = BeliefMap.from_world(world)
    names = [nm for nm in world.objects if goal_cells_for(belief, nm)]
    tasks, tries = [], 0
    while len(tasks) < n and tries < 4000 and names:
        tries += 1
        s = tuple(int(x) for x in free[rng.integers(len(free))])
        goal = names[rng.integers(len(names))]
        goals = goal_cells_for(belief, goal)
        a = world.objects[goal].anchor
        if abs(s[0] - a[0]) + abs(s[1] - a[1]) < min_dist:
            continue
        if astar(world.is_free, s, goals, world.shape) is None:
            continue
        tasks.append({"id": f"t{len(tasks)}", "start": list(s), "goal": goal})
    return tasks


def _chokepoint(world: TrueWorld, tasks: List[dict]) -> Cell:
    """Free cell used by the most optimal paths, preferring narrow spots."""
    from ..agents import goal_cells_for
    belief = BeliefMap.from_world(world)
    use = np.zeros(world.shape, np.int32)
    for t in tasks:
        p = astar(world.is_free, tuple(t["start"]), goal_cells_for(belief, t["goal"]), world.shape)
        if p:
            for c in p[3:-3]:
                use[c] += 1
    if use.max() == 0:
        free = np.argwhere(world.grid == FREE)
        return tuple(int(x) for x in free[len(free) // 2])
    # narrowness: number of occupied/unknown cells in a 5x5 window
    blocked = (world.grid != FREE).astype(np.int32)
    narrow = ndimage.uniform_filter(blocked.astype(float), 5)
    score = use * (1 + 3 * narrow)
    return tuple(int(x) for x in np.unravel_index(int(np.argmax(score)), score.shape))


def _far_free_cell(world: TrueWorld, avoid: Cell, obj_cells: int) -> Cell:
    main = _largest_free_component(world.grid)
    free = np.argwhere(main)
    d = np.abs(free[:, 0] - avoid[0]) + np.abs(free[:, 1] - avoid[1])
    # pick a cell in the far 40% that has room around it
    idx = np.argsort(-d)[: max(1, len(free) // 3)]
    rng = np.random.default_rng(1)
    for i in rng.permutation(idx):
        r, c = free[i]
        win = world.grid[max(0, r - 2):r + 3, max(0, c - 2):c + 3]
        if (win == FREE).mean() > 0.7:
            return (int(r), int(c))
    return tuple(int(x) for x in free[idx[0]])


def _block_cell(world: TrueWorld, obj_name: str, cell: Cell) -> dict:
    old = world.objects[obj_name].anchor
    world.move_object(obj_name, cell)
    return {"kind": "block_chokepoint", "object": obj_name, "from": list(old), "to": list(cell)}


def auto_perturbations(world: TrueWorld, tasks: List[dict]) -> List[dict]:
    """Generic 3-round script for a scanned map: block a chokepoint, move a goal object, un-block (stale map)."""
    if not world.objects:
        return []
    by_size = sorted(world.objects.values(), key=lambda o: len(o.cells))
    small, big = by_size[0], by_size[-1]
    chk = _chokepoint(world, tasks)
    far = _far_free_cell(world, big.anchor, len(big.cells))
    return [
        {"fn": _block_cell, "args": [small.name, chk], "story": f"The {small.name} was left in the busiest corridor (chokepoint at {chk})."},
        {"fn": relocate_object, "args": [big.name, far], "story": f"The {big.name} was moved to the other side of the space ({far})."},
        {"fn": relocate_object, "args": [small.name, small.anchor], "story": f"The {small.name} was put back: the corridor is open again but the map still thinks it is blocked."},
    ]


@weave.op
def scan_to_world(video: str, out_dir: str, n_frames: int = 48, cell: float = 0.15, detect_every: int = 2,
                  unknown_is_blocked: bool = True) -> Tuple[TrueWorld, BeliefMap, List[dict]]:
    sd = os.path.join(out_dir, "scan")
    os.makedirs(sd, exist_ok=True)
    t0 = time.time()
    frames = extract_frames(video, os.path.join(sd, "frames"), n=n_frames)
    contact_sheet(frames, os.path.join(sd, "contact_sheet.jpg"))
    print(f"[scan] {len(frames)} keyframes extracted ({time.time()-t0:.1f}s)")
    npz = os.path.join(sd, "vggt_out.npz")
    if not os.path.exists(npz) or os.environ.get("COGMAP_FORCE_VGGT"):
        tm = run_vggt(frames, npz, max_frames=n_frames)
        print(f"[scan] VGGT on Modal: {tm}")
    g = build_grid(npz, cell=cell)
    grid = _clean_grid(g["grid"])
    save_grid_png(grid, os.path.join(sd, "occupancy_grid.png"))
    np.save(os.path.join(sd, "points_xyz.npy"), g["points_xyz"])
    json.dump({k: v for k, v in g.items() if k not in ("grid", "points_xyz")}, open(os.path.join(sd, "grid_meta.json"), "w"))
    print(f"[scan] grid {grid.shape} cell={cell}m stats={g['stats']} frame={g['frame']['note']} ({time.time()-t0:.1f}s)")
    # semantic objects
    objects: Dict[str, WorldObject] = {}
    try:
        det_path = os.path.join(sd, "detections.json")
        if os.path.exists(det_path) and not os.environ.get("COGMAP_FORCE_DETECT"):
            dets = json.load(open(det_path))
        else:
            dets = detect_all(frames, every=detect_every)
            json.dump(dets, open(det_path, "w"))
        anc = anchor_objects(dets, npz, frames, {**g, "grid": grid}, every=detect_every)
        objects = {k: WorldObject.from_json(v) for k, v in anc["objects"].items()}
        print(f"[scan] objects: {len(objects)} from {anc['n_candidates']} detections ({time.time()-t0:.1f}s): {list(objects)[:10]}")
    except Exception as e:  # noqa: BLE001
        print("[scan] object detection failed:", e)
    if len(objects) < 4:
        objects = blobs_as_objects(grid, objects)
        print(f"[scan] added blob landmarks -> {list(objects)}")
    # world: what the robot will actually bump into. Unknown = never observed = treated as blocked (conservative).
    static = grid.copy()
    for o in objects.values():
        for c in o.cells:
            if 0 <= c[0] < static.shape[0] and 0 <= c[1] < static.shape[1]:
                static[c] = FREE   # object footprints are stamped by TrueWorld; keep static = walls/unknown only
    if unknown_is_blocked:
        static[static == UNKNOWN] = OCCUPIED
    world = TrueWorld(static, objects, name=os.path.splitext(os.path.basename(video))[0])
    # belief: exactly what the scan says (keeps UNKNOWN cells unknown -> agents may try and learn)
    belief_grid = grid.copy()
    belief = BeliefMap(belief_grid, {k: WorldObject(v.name, list(v.cells), v.kind, v.confidence) for k, v in objects.items()},
                       name=world.name)
    for o in belief.objects.values():
        belief.stamp_object(o, OCCUPIED, o.confidence)
    belief.save(os.path.join(sd, "belief_v0.json"))
    tasks = reachable_tasks(world)
    perts = auto_perturbations(world, tasks)
    ex = export_nav2(belief, os.path.join(sd, "nav2"), resolution=cell, origin_xy=tuple(g["origin_xy"]))
    print(f"[scan] nav2 export: {ex}  tasks={len(tasks)} perturbations={len(perts)} total {time.time()-t0:.1f}s")
    return world, belief, perts
