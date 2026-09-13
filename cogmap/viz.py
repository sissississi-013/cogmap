"""Visualisations: success curve, map snapshots, swarm animation (MP4), 3D point cloud (HTML)."""
from __future__ import annotations

import json
import os
from typing import List, Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import animation, colors

from .world import UNKNOWN, FREE, OCCUPIED

CMAP = colors.ListedColormap(["#9aa0a6", "#f7f7f5", "#2b2d42"])  # unknown, free, occupied
NORM = colors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5], CMAP.N)


def plot_curve(out_dir: str) -> str:
    with open(os.path.join(out_dir, "loop_result.json")) as f:
        res = json.load(f)
    tl = res["timeline"]
    x = list(range(len(tl)))
    succ = [m["success_rate"] for m in tl]
    spl = [m["spl"] for m in tl]
    labels = [m["label"] for m in tl]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(x, succ, "-o", color="#1f77b4", lw=2.5, label="navigation success rate")
    ax.plot(x, spl, "--s", color="#ff7f0e", lw=1.5, ms=4, label="SPL (path efficiency)")
    for i, m in enumerate(tl):
        if m.get("phase") == "after_change":
            ax.axvline(i, color="#d62728", alpha=0.25, lw=8)
            ax.text(i, 1.06, f"change {m.get('round')}", ha="center", fontsize=8, color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels([l.replace("-", "\n", 1) for l in labels], fontsize=7)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("score on fixed task set")
    ax.set_title("CogMap: the world changes (red) → swarm fails → map repaired → success recovers")
    ax.legend(loc="lower left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p = os.path.join(out_dir, "curve.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    # steps-to-recover per round (outer-loop metric)
    rounds = res.get("rounds", [])
    if rounds:
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.bar([f"round {r['round']}" for r in rounds], [r["steps_to_recover"] for r in rounds], color="#2ca02c")
        ax.set_ylabel("agent steps until success recovered")
        ax.set_title("Self-improving swarm: steps-to-recover per change")
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "steps_to_recover.png"), dpi=150)
        plt.close(fig)
    return p


def _draw_frame(ax_b, ax_t, fr, title_extra=""):
    belief = np.array(fr["belief"]); true = np.array(fr["true"])
    for ax in (ax_b, ax_t):
        ax.clear(); ax.set_xticks([]); ax.set_yticks([])
    ax_b.imshow(belief, cmap=CMAP, norm=NORM, interpolation="nearest")
    ax_t.imshow(true, cmap=CMAP, norm=NORM, interpolation="nearest")
    vol = np.array(fr.get("volatility", np.zeros_like(belief)), dtype=float)
    if vol.max() > 0:
        ax_b.imshow(np.ma.masked_where(vol < 0.05, vol), cmap="Oranges", alpha=0.55, vmin=0, vmax=1, interpolation="nearest")
    for name, o in fr["objects"].items():
        a = o["anchor"]
        ax_b.text(a[1], a[0], name.replace("unknown_obstacle", "?obst"), fontsize=5, ha="center", va="center", color="#ffd166",
                  bbox=dict(boxstyle="round,pad=0.15", fc="#2b2d42", ec="none", alpha=0.8))
    ax_b.set_title(f"belief map v{fr['version']}  (orange = volatility prior)", fontsize=9)
    ax_t.set_title("true world (agents' paths, red X = failures)" + title_extra, fontsize=9)


def animate(out_dir: str, fps: int = 12, steps_per_frame: int = 4) -> Optional[str]:
    with open(os.path.join(out_dir, "frames.json")) as f:
        frames = json.load(f)
    if not frames:
        return None
    fig, (ax_b, ax_t) = plt.subplots(1, 2, figsize=(12, 4.2))
    seq = []  # (frame index, t)
    for i, fr in enumerate(frames):
        max_len = max([len(p) for p in fr["paths"]] + [len(fr.get("patrol_path", []))] + [1])
        n_t = max(8, (max_len + steps_per_frame - 1) // steps_per_frame + 6)
        for t in range(n_t):
            seq.append((i, t * steps_per_frame))
    cols = plt.cm.tab10(np.linspace(0, 1, 10))
    banner = fig.text(0.5, 0.97, "", ha="center", va="top", fontsize=11, weight="bold")

    def draw(k):
        i, t = seq[k]
        fr = frames[i]
        _draw_frame(ax_b, ax_t, fr)
        banner.set_text(fr["label"])
        for j, p in enumerate(fr["paths"]):
            p = np.array(p)
            if len(p) == 0:
                continue
            seg = p[:t + 1]
            ax_t.plot(seg[:, 1], seg[:, 0], "-", color=cols[j % 10], lw=1.2, alpha=0.8)
            ax_t.plot(seg[-1, 1], seg[-1, 0], "o", color=cols[j % 10], ms=5)
        pp = np.array(fr.get("patrol_path", []))
        if len(pp):
            seg = pp[:t + 1]
            ax_t.plot(seg[:, 1], seg[:, 0], "-", color="#ff7f0e", lw=2, alpha=0.9)
            ax_t.plot(seg[-1, 1], seg[-1, 0], "D", color="#ff7f0e", ms=6)
            ax_t.text(seg[-1, 1], seg[-1, 0] - 1.2, "patrol", fontsize=6, color="#ff7f0e", ha="center")
        for fl in fr["failures"]:
            if fl["step"] <= t:
                ax_t.plot(fl["cell"][1], fl["cell"][0], "x", color="red", ms=7, mew=2)
        return []

    ani = animation.FuncAnimation(fig, draw, frames=len(seq), interval=1000 / fps, blit=False)
    p = os.path.join(out_dir, "swarm.mp4")
    ani.save(p, writer="ffmpeg", fps=fps, dpi=110)
    plt.close(fig)
    return p


def snapshots(out_dir: str) -> List[str]:
    with open(os.path.join(out_dir, "frames.json")) as f:
        frames = json.load(f)
    paths = []
    for i, fr in enumerate(frames):
        fig, (ax_b, ax_t) = plt.subplots(1, 2, figsize=(12, 4.2))
        _draw_frame(ax_b, ax_t, fr)
        cols = plt.cm.tab10(np.linspace(0, 1, 10))
        for j, p in enumerate(fr["paths"]):
            p = np.array(p)
            if len(p):
                ax_t.plot(p[:, 1], p[:, 0], "-", color=cols[j % 10], lw=1, alpha=0.7)
        for fl in fr["failures"]:
            ax_t.plot(fl["cell"][1], fl["cell"][0], "x", color="red", ms=7, mew=2)
        fig.suptitle(fr["label"], fontsize=11, weight="bold")
        fig.tight_layout()
        p = os.path.join(out_dir, f"snapshot_{i:02d}.png")
        fig.savefig(p, dpi=120); plt.close(fig)
        paths.append(p)
    return paths


def render_all(out_dir: str):
    print("curve:", plot_curve(out_dir))
    print("snapshots:", len(snapshots(out_dir)))
    try:
        print("animation:", animate(out_dir))
    except Exception as e:  # noqa: BLE001
        print("animation failed:", e)


def pointcloud_html(points_xyz, cam_traj_xy, out_path: str, title: str = "CogMap world model (VGGT point map)") -> str:
    import plotly.graph_objects as go
    P = np.asarray(points_xyz)
    if len(P) > 60000:
        P = P[np.random.default_rng(0).choice(len(P), 60000, replace=False)]
    cam = np.asarray(cam_traj_xy)
    fig = go.Figure()
    fig.add_trace(go.Scatter3d(x=P[:, 0], y=P[:, 1], z=P[:, 2], mode="markers",
                               marker=dict(size=1.6, color=np.clip(P[:, 2], -0.3, 2.5), colorscale="Viridis", opacity=0.8),
                               name="points"))
    if len(cam):
        fig.add_trace(go.Scatter3d(x=cam[:, 0], y=cam[:, 1], z=np.full(len(cam), 1.4), mode="lines+markers",
                                   line=dict(color="red", width=5), marker=dict(size=3, color="red"), name="phone path"))
    fig.update_layout(title=title, scene=dict(aspectmode="data", xaxis_title="x (m)", yaxis_title="y (m)", zaxis_title="height (m)"),
                      margin=dict(l=0, r=0, t=40, b=0), template="plotly_dark")
    fig.write_html(out_path, include_plotlyjs="cdn")
    return out_path


def scan_overview(scan_dir: str, out_path: Optional[str] = None) -> str:
    """Grid + object labels + phone path for a scanned space (reads scan/belief_v0.json + grid_meta.json)."""
    import json as _json
    from .world import BeliefMap
    b = BeliefMap.load(os.path.join(scan_dir, "belief_v0.json"))
    meta = _json.load(open(os.path.join(scan_dir, "grid_meta.json")))
    fig, ax = plt.subplots(figsize=(9, 9 * b.shape[0] / max(b.shape[1], 1)))
    ax.imshow(b.grid, cmap=CMAP, norm=NORM, interpolation="nearest")
    cells = np.array(meta.get("cam_traj_cells", []))
    if len(cells):
        ax.plot(cells[:, 1], cells[:, 0], "-", color="#e63946", lw=2, label="phone path")
        ax.plot(cells[0, 1], cells[0, 0], "o", color="#e63946", ms=8)
    for name, o in b.objects.items():
        a = o.anchor
        ax.text(a[1], a[0], name, fontsize=7, ha="center", va="center", color="#ffd166",
                bbox=dict(boxstyle="round,pad=0.2", fc="#2b2d42", ec="none", alpha=0.85))
    ax.set_title(f"CogMap v0 from phone scan: {b.shape[1]}x{b.shape[0]} cells @ {meta.get('cell', 0.15)} m — "
                 f"white=free, black=occupied, grey=unknown", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([]); ax.legend(loc="lower right", fontsize=8)
    out_path = out_path or os.path.join(scan_dir, "scan_overview.png")
    fig.tight_layout(); fig.savefig(out_path, dpi=130); plt.close(fig)
    return out_path



def log_images_to_weave(out_dir: str) -> dict:
    """Publish the run's key images as Weave objects (they render inline in the trace / object views)."""
    import weave
    from PIL import Image

    @weave.op
    def cogmap_run_images(run: str) -> dict:
        imgs = {}
        for name in ("curve.png", "steps_to_recover.png", os.path.join("scan", "scan_overview.png"), "snapshot_01.png"):
            p = os.path.join(run, name)
            if os.path.exists(p):
                imgs[os.path.basename(name).replace(".png", "")] = Image.open(p).convert("RGB")
        return imgs

    out = cogmap_run_images(out_dir)
    try:
        weave.publish(out, name=f"cogmap-images-{os.path.basename(out_dir.rstrip('/'))}")
    except Exception as e:  # noqa: BLE001
        print("weave publish of images failed:", e)
    return {k: v.size for k, v in out.items()}
