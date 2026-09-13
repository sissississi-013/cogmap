import os

import numpy as np

from cogmap.scan.grid import build_grid, world_to_cell
from cogmap.world import FREE, OCCUPIED, UNKNOWN


def _synthetic_npz(path, S=6, H=40, W=60):
    """Camera looking down at a floor (z=0) with a 1 m tall box; camera 1.4 m up, moving along +x."""
    rng = np.random.default_rng(0)
    depth = np.zeros((S, H, W), np.float32); conf = np.ones((S, H, W), np.float32) * 2
    pts = np.zeros((S, H, W, 3), np.float32)
    ext = np.zeros((S, 3, 4)); intr = np.tile(np.array([[50, 0, W / 2], [0, 50, H / 2], [0, 0, 1]], float), (S, 1, 1))
    for s in range(S):
        cam_x = 0.5 * s
        # world->cam: upright phone at (cam_x, 0, 1.4) looking along +x. OpenCV cam axes: x right = world -y,
        # y down = world -z, z forward = world +x  => camera "up" (-y_cam) is world +z.
        R = np.array([[0, -1, 0], [0, 0, -1], [1, 0, 0]], float)
        C = np.array([cam_x, 0.0, 1.4])
        ext[s, :, :3] = R; ext[s, :, 3] = -R @ C
        # sample world points on the floor in front of the camera (3 m x 3 m patch) + a 1 m tall box
        xs = cam_x + rng.uniform(0.5, 3.5, (H, W)); ys = rng.uniform(-1.5, 1.5, (H, W))
        zs = np.zeros((H, W))
        box = (xs > 2.0) & (xs < 2.6) & (ys > -0.3) & (ys < 0.3)
        zs[box] = 1.0
        pts[s, :, :, 0] = xs; pts[s, :, :, 1] = ys; pts[s, :, :, 2] = zs
        depth[s] = 1.4 - zs
    np.savez_compressed(path, extrinsic=ext, intrinsic=intr, depth=depth, depth_conf=conf, world_points=pts,
                        world_points_conf=conf, world_points_from_depth=pts, images=np.zeros((S, H, W, 3), np.uint8),
                        timings=np.array([0, 0, 0, 0.0]))


def test_build_grid_recovers_floor_and_box(tmp_path):
    p = os.path.join(tmp_path, "fake.npz")
    _synthetic_npz(p)
    g = build_grid(p, cell=0.15, max_radius_m=3.0)
    grid = g["grid"]
    assert g["stats"]["free"] > 100 and g["stats"]["occupied"] > 5
    # the box (x in 2.0..2.6, y in -0.3..0.3) should be occupied; a floor spot at (1.5, -1.0) free
    s = g["frame"]["scale"]
    r, c = world_to_cell([2.3, 0.0, 0.5], g["frame"], g["origin_xy"], 0.15); assert grid[r, c] == OCCUPIED
    r, c = world_to_cell([1.5, -1.0, 0.0], g["frame"], g["origin_xy"], 0.15); assert grid[r, c] == FREE
    assert abs(s - 1.0) < 0.05   # camera height was 1.4 m -> scale ~1
    assert len(g["cam_traj_xy"]) == 6 and g["frame"]["fallback_plane"] is False
