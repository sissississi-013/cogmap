"""Build a 2D occupancy grid + top-down scatter + camera trajectory from VGGT output.

Usage: python3 make_grid.py out/vggt_out.npz out/
Outputs: occupancy_grid.png, occupancy_grid.json, topdown_scatter.png, grid_with_trajectory.png
"""
import sys, os, json, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cv2

npz_path, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
d = np.load(npz_path)
ext = d["extrinsic"].astype(np.float64)          # (S,3,4) world->cam
pts = d["world_points_from_depth"].astype(np.float64)  # (S,H,W,3) points from depth+cams
conf = d["depth_conf"].astype(np.float64)        # (S,H,W)
S, H, W = conf.shape
print(f"frames={S} HxW={H}x{W}")

# ---- camera centers + camera "up"/"forward" in world coords
R = ext[:, :, :3]; t = ext[:, :, 3]
cam_c = -np.einsum("sji,sj->si", R, t)           # C = -R^T t
cam_up_world = -R[:, 1, :]                       # OpenCV cam y is down -> up = -row1 of R (R^T @ [0,-1,0])
mean_up = cam_up_world.mean(0); mean_up /= np.linalg.norm(mean_up)

# ---- confidence filter
P = pts.reshape(-1, 3); C = conf.reshape(-1)
finite = np.isfinite(P).all(1)
thr = np.percentile(C[finite], 50)               # keep upper half by confidence (VGGT conf is >=1; static clips stay near 1.0)
keep = finite & (C > thr)
if keep.sum() < 0.1 * finite.sum(): keep = finite & (C >= thr)   # all-tied confidences: keep everything
P = P[keep]
print(f"kept {keep.sum()}/{keep.size} points (conf >= {thr:.2f})")
if len(P) > 400_000:
    P = P[np.random.default_rng(0).choice(len(P), 400_000, replace=False)]

# ---- ground plane: RANSAC on points whose height along camera-up is in the bottom part
def ransac_plane(X, n_iter=300, tol=None, rng=np.random.default_rng(0)):
    if tol is None:
        tol = 0.02 * np.median(np.linalg.norm(X - X.mean(0), axis=1))
    best = (0, None)
    for _ in range(n_iter):
        i = rng.choice(len(X), 3, replace=False)
        a, b, c = X[i]
        n = np.cross(b - a, c - a); nn = np.linalg.norm(n)
        if nn < 1e-9: continue
        n /= nn
        dist = np.abs((X - a) @ n)
        inl = (dist < tol).sum()
        if inl > best[0]: best = (inl, (n, a))
    n, a = best[1]
    inl = np.abs((X - a) @ n) < tol
    Xi = X[inl]; ctr = Xi.mean(0)
    _, _, vt = np.linalg.svd(Xi - ctr, full_matrices=False)
    n = vt[2]
    return n, ctr, inl.sum()

h_up = P @ mean_up
low = P[h_up < np.percentile(h_up, 30)]           # candidate floor points: lowest 30% along camera-up
n, ctr, n_inl = ransac_plane(low)
if n @ mean_up < 0: n = -n                        # orient plane normal to point "up"
angle = np.degrees(np.arccos(np.clip(n @ mean_up, -1, 1)))
print(f"ground plane: normal·cam_up = {n@mean_up:.3f} ({angle:.1f} deg off camera-up), inliers={n_inl}")
# Sanity: if RANSAC plane disagrees wildly with camera-up (>35 deg), fall back to camera-up + low percentile
if angle > 35:
    print("  plane too far from camera-up; falling back to camera-up axis")
    n = mean_up; ctr = P[np.argmin(np.abs(h_up - np.percentile(h_up, 5)))]

# ---- build frame: z = up (n), x/y in plane
z = n
x = np.cross([0, 0, 1.0], z) if abs(z[2]) < 0.9 else np.cross([1.0, 0, 0], z)
x /= np.linalg.norm(x); y = np.cross(z, x)
Rw = np.stack([x, y, z])                          # rows = new axes
Pl = (P - ctr) @ Rw.T                             # (N,3): x,y in floor plane, z = height above floor
cam_l = (cam_c - ctr) @ Rw.T

# ---- scale: VGGT is up to scale. Normalise so median camera height above floor = 1.4 m
cam_h = np.median(cam_l[:, 2])
extent = np.percentile(np.linalg.norm(Pl[:, :2] - np.median(Pl[:, :2], 0), axis=1), 95)
if cam_h > 0.05 * extent:
    scale = 1.4 / cam_h
else:  # camera-height estimate unusable (e.g. floor not visible / camera static): fall back to "scene radius ~= 3 m"
    scale = 3.0 / extent
    print(f"  camera-height scale unusable (cam_h={cam_h:.3f}, extent={extent:.3f}); falling back to scene-extent scale")
print(f"median camera height (raw units) = {cam_h:.3f} -> scale factor {scale:.3f} (assumes camera ~1.4 m above floor)")
Pl *= scale; cam_l *= scale

# ---- occupancy grid
cell = 0.10  # m
hz = Pl[:, 2]
floor_m = (hz > -0.15) & (hz < 0.15)
obst_m = (hz >= 0.15) & (hz <= 1.8)
xy = Pl[:, :2]
lo = np.minimum(np.percentile(xy, 1, axis=0), cam_l[:, :2].min(0)) - 0.5; hi = np.maximum(np.percentile(xy, 99, axis=0), cam_l[:, :2].max(0)) + 0.5
inb = (xy[:, 0] >= lo[0]) & (xy[:, 0] < hi[0]) & (xy[:, 1] >= lo[1]) & (xy[:, 1] < hi[1])
nx, ny = (np.ceil((hi - lo) / cell)).astype(int)
def to_cell(p): return ((p - lo) / cell).astype(int)
grid = np.zeros((ny, nx), np.uint8)              # 0 unknown, 1 free, 2 occupied
fc = to_cell(xy[floor_m & inb]); oc = to_cell(xy[obst_m & inb])
floor_cnt = np.zeros_like(grid, np.int32); obst_cnt = np.zeros_like(grid, np.int32)
np.add.at(floor_cnt, (fc[:, 1], fc[:, 0]), 1); np.add.at(obst_cnt, (oc[:, 1], oc[:, 0]), 1)
grid[floor_cnt >= 3] = 1
grid[obst_cnt >= 5] = 2
print(f"grid {nx}x{ny} cells @ {cell} m: free={int((grid==1).sum())} occ={int((grid==2).sum())} unknown={int((grid==0).sum())}")

# PNG: unknown=gray(128), free=white(255), occupied=black(0)
img = np.full(grid.shape, 128, np.uint8); img[grid == 1] = 255; img[grid == 2] = 0
img = np.flipud(img)                              # row 0 = max y (north up)
up = max(1, 800 // max(nx, ny))
cv2.imwrite(os.path.join(out_dir, "occupancy_grid.png"), cv2.resize(img, (nx * up, ny * up), interpolation=cv2.INTER_NEAREST))
traj = (cam_l[:, :2]).tolist()
json.dump({
    "cell_size_m": cell, "origin_xy_m": lo.tolist(), "width": int(nx), "height": int(ny),
    "encoding": {"0": "unknown", "1": "free", "2": "occupied"}, "row0_is_min_y": True,
    "scale_note": "VGGT scale is arbitrary; normalised so median camera height = 1.4 m",
    "scale_factor_applied": float(scale), "ground_normal_world": n.tolist(), "ground_point_world": ctr.tolist(),
    "camera_trajectory_xy_m": traj, "camera_height_m": (cam_l[:, 2]).tolist(),
    "grid": grid.tolist(),
}, open(os.path.join(out_dir, "occupancy_grid.json"), "w"))

# ---- top-down scatter coloured by height
sub = Pl[np.random.default_rng(1).choice(len(Pl), min(len(Pl), 150_000), replace=False)]
fig, ax = plt.subplots(figsize=(9, 9))
sc = ax.scatter(sub[:, 0], sub[:, 1], c=np.clip(sub[:, 2], -0.5, 2.5), s=0.3, cmap="viridis")
ax.plot(cam_l[:, 0], cam_l[:, 1], "r-", lw=1.5, label="camera path"); ax.scatter(cam_l[0, 0], cam_l[0, 1], c="r", marker="o", s=60, label="start")
ax.set_aspect("equal"); ax.set_xlabel("x (m, normalised)"); ax.set_ylabel("y (m, normalised)"); ax.legend()
plt.colorbar(sc, label="height above floor (m)"); ax.set_title("VGGT point map, top-down, coloured by height")
fig.savefig(os.path.join(out_dir, "topdown_scatter.png"), dpi=120, bbox_inches="tight"); plt.close(fig)

# ---- grid with trajectory overlay
fig, ax = plt.subplots(figsize=(9, 9))
ax.imshow(img, cmap="gray", vmin=0, vmax=255, extent=[lo[0], lo[0] + nx * cell, lo[1], lo[1] + ny * cell], origin="upper")
ax.plot(cam_l[:, 0], cam_l[:, 1], "r-", lw=2, label="camera path")
ax.scatter(cam_l[:, 0], cam_l[:, 1], c=np.arange(S), cmap="autumn", s=25, zorder=3)
ax.scatter(cam_l[0, 0], cam_l[0, 1], c="lime", s=80, zorder=4, label="start")
ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.legend(); ax.set_title("Occupancy grid (white=free, black=occupied, gray=unknown) + camera trajectory")
fig.savefig(os.path.join(out_dir, "grid_with_trajectory.png"), dpi=120, bbox_inches="tight"); plt.close(fig)

# ---- one depth preview for sanity
dep = d["depth"][0].astype(np.float32); dep = (255 * (dep - dep.min()) / (np.ptp(dep) + 1e-9)).astype(np.uint8)
cv2.imwrite(os.path.join(out_dir, "depth_frame0.png"), np.hstack([cv2.cvtColor(d["images"][0], cv2.COLOR_RGB2BGR), cv2.applyColorMap(dep, cv2.COLORMAP_TURBO)]))
print("wrote", sorted(os.listdir(out_dir)))
