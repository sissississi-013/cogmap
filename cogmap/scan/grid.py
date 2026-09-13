"""VGGT output (.npz) -> floor frame -> 2D occupancy grid (+ point cloud subsample for viz).

Ported from spikes/vggt_modal/make_grid.py. Grid encoding: 0 unknown, 1 free, 2 occupied.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Tuple

import numpy as np


def _ransac_plane(X, n_iter=300, tol=None, rng=np.random.default_rng(0)):
    if tol is None:
        tol = 0.02 * np.median(np.linalg.norm(X - X.mean(0), axis=1))
    best = (0, None)
    for _ in range(n_iter):
        i = rng.choice(len(X), 3, replace=False)
        a, b, c = X[i]
        n = np.cross(b - a, c - a); nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue
        n /= nn
        inl = (np.abs((X - a) @ n) < tol).sum()
        if inl > best[0]:
            best = (inl, (n, a))
    n, a = best[1]
    inl = np.abs((X - a) @ n) < tol
    Xi = X[inl]; ctr = Xi.mean(0)
    _, _, vt = np.linalg.svd(Xi - ctr, full_matrices=False)
    return vt[2], ctr, int(inl.sum())


def build_grid(npz_path: str, cell: float = 0.15, camera_height_m: float = 1.4, max_points: int = 400_000) -> Dict:
    """Returns dict with grid (H,W) uint8, origin_xy, cell, cam_traj_xy, frame transform, and a point subsample."""
    d = np.load(npz_path)
    ext = d["extrinsic"].astype(np.float64)
    pts = d["world_points_from_depth"].astype(np.float64)
    conf = d["depth_conf"].astype(np.float64)
    S, H, W = conf.shape
    R = ext[:, :, :3]; t = ext[:, :, 3]
    cam_c = -np.einsum("sji,sj->si", R, t)
    cam_up_world = -R[:, 1, :]
    mean_up = cam_up_world.mean(0); mean_up /= np.linalg.norm(mean_up)

    P = pts.reshape(-1, 3); C = conf.reshape(-1)
    finite = np.isfinite(P).all(1)
    thr = np.percentile(C[finite], 50)
    keep = finite & (C > thr)
    if keep.sum() < 0.1 * finite.sum():
        keep = finite & (C >= thr)
    # remember pixel -> point index for object anchoring
    P = P[keep]
    rng = np.random.default_rng(0)
    if len(P) > max_points:
        P = P[rng.choice(len(P), max_points, replace=False)]

    h_up = P @ mean_up
    low = P[h_up < np.percentile(h_up, 30)]
    n, ctr, n_inl = _ransac_plane(low)
    if n @ mean_up < 0:
        n = -n
    angle = float(np.degrees(np.arccos(np.clip(n @ mean_up, -1, 1))))
    fallback_plane = angle > 35
    if fallback_plane:
        n = mean_up; ctr = P[np.argmin(np.abs(h_up - np.percentile(h_up, 5)))]
    z = n
    x = np.cross([0, 0, 1.0], z) if abs(z[2]) < 0.9 else np.cross([1.0, 0, 0], z)
    x /= np.linalg.norm(x); y = np.cross(z, x)
    Rw = np.stack([x, y, z])
    Pl = (P - ctr) @ Rw.T
    cam_l = (cam_c - ctr) @ Rw.T
    cam_h = float(np.median(cam_l[:, 2]))
    extent = float(np.percentile(np.linalg.norm(Pl[:, :2] - np.median(Pl[:, :2], 0), axis=1), 95))
    if cam_h > 0.05 * extent:
        scale = camera_height_m / cam_h; scale_note = f"camera height normalised to {camera_height_m} m"
    else:
        scale = 3.0 / extent; scale_note = "camera-height unusable; scene radius normalised to 3 m"
    Pl *= scale; cam_l *= scale

    hz = Pl[:, 2]
    floor_m = (hz > -0.15) & (hz < 0.15)
    obst_m = (hz >= 0.15) & (hz <= 1.8)
    xy = Pl[:, :2]
    lo = np.minimum(np.percentile(xy, 1, axis=0), cam_l[:, :2].min(0)) - 0.5
    hi = np.maximum(np.percentile(xy, 99, axis=0), cam_l[:, :2].max(0)) + 0.5
    inb = (xy[:, 0] >= lo[0]) & (xy[:, 0] < hi[0]) & (xy[:, 1] >= lo[1]) & (xy[:, 1] < hi[1])
    nx, ny = (np.ceil((hi - lo) / cell)).astype(int)
    nx, ny = int(min(nx, 400)), int(min(ny, 400))

    def to_cell(p):
        return ((p - lo) / cell).astype(int)

    grid = np.zeros((ny, nx), np.uint8)
    fc = to_cell(xy[floor_m & inb]); oc = to_cell(xy[obst_m & inb])
    fc = fc[(fc[:, 0] < nx) & (fc[:, 1] < ny)]; oc = oc[(oc[:, 0] < nx) & (oc[:, 1] < ny)]
    floor_cnt = np.zeros_like(grid, np.int32); obst_cnt = np.zeros_like(grid, np.int32)
    np.add.at(floor_cnt, (fc[:, 1], fc[:, 0]), 1); np.add.at(obst_cnt, (oc[:, 1], oc[:, 0]), 1)
    grid[floor_cnt >= 3] = 1
    grid[obst_cnt >= 5] = 2
    # the camera walked here: those cells are free for sure
    cc = to_cell(cam_l[:, :2])
    for cx, cy in cc:
        if 0 <= cx < nx and 0 <= cy < ny:
            grid[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2] = np.where(grid[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2] == 2, 2, 1)
            grid[cy, cx] = 1

    sub_idx = rng.choice(len(Pl), min(len(Pl), 60_000), replace=False)
    return {
        "grid": grid, "cell": cell, "origin_xy": lo.tolist(), "width": nx, "height": ny,
        "cam_traj_xy": cam_l[:, :2].tolist(), "cam_traj_cells": [[int(c[1]), int(c[0])] for c in cc],
        "frame": {"R": Rw.tolist(), "ctr": ctr.tolist(), "scale": float(scale), "note": scale_note,
                  "ground_plane_angle_deg": angle, "fallback_plane": fallback_plane},
        "points_xyz": Pl[sub_idx].astype(np.float32), "n_points": int(len(Pl)),
        "stats": {"free": int((grid == 1).sum()), "occupied": int((grid == 2).sum()), "unknown": int((grid == 0).sum())},
    }


def world_to_cell(xyz_world: np.ndarray, frame: dict, origin_xy, cell: float) -> Tuple[int, int]:
    """Map a world-space point (VGGT coords) to (row, col) in the grid."""
    Rw = np.array(frame["R"]); ctr = np.array(frame["ctr"]); s = frame["scale"]
    p = (np.asarray(xyz_world, dtype=np.float64) - ctr) @ Rw.T * s
    c = int((p[0] - origin_xy[0]) / cell); r = int((p[1] - origin_xy[1]) / cell)
    return r, c


def save_grid_png(grid: np.ndarray, path: str, upscale: int = 6):
    import cv2
    img = np.full(grid.shape, 128, np.uint8); img[grid == 1] = 255; img[grid == 2] = 0
    cv2.imwrite(path, cv2.resize(img, (grid.shape[1] * upscale, grid.shape[0] * upscale), interpolation=cv2.INTER_NEAREST))
