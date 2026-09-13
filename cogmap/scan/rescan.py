"""Re-scan loop closure: register a SECOND phone walkthrough (after furniture moved) to the first map and turn the
difference into observations for the repair agent. This is the real-world version of the perturbation loop.

Registration: brute-force rotation (2°) x scale {0.9,1,1.1} with FFT cross-correlation of occupied masks for translation.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

import numpy as np
from scipy import ndimage

from ..world import BeliefMap, UNKNOWN, FREE, OCCUPIED


def _mask(grid: np.ndarray, value: int) -> np.ndarray:
    return (grid == value).astype(np.float32)


def _xcorr_best(a: np.ndarray, b: np.ndarray) -> Tuple[float, Tuple[int, int]]:
    """Max normalized cross-correlation of b over a (same shape, zero-padded); returns (score, (dr, dc))."""
    H, W = a.shape
    fa = np.fft.rfft2(a, s=(2 * H, 2 * W)); fb = np.fft.rfft2(b, s=(2 * H, 2 * W))
    cc = np.fft.irfft2(fa * np.conj(fb), s=(2 * H, 2 * W))
    idx = np.unravel_index(int(np.argmax(cc)), cc.shape)
    dr = idx[0] if idx[0] < H else idx[0] - 2 * H
    dc = idx[1] if idx[1] < W else idx[1] - 2 * W
    norm = float(np.sqrt((a ** 2).sum() * (b ** 2).sum())) + 1e-9
    return float(cc[idx] / norm), (int(dr), int(dc))


def register(grid_a: np.ndarray, grid_b: np.ndarray, angles=range(0, 360, 2), scales=(0.9, 1.0, 1.1)) -> Dict:
    """Find (angle, scale, shift) that best aligns B's occupied mask to A's. Returns params + aligned B grid in A's frame."""
    H, W = grid_a.shape
    A = _mask(grid_a, OCCUPIED)
    best = {"score": -1}
    for s in scales:
        for ang in angles:
            # rotate+scale B about its centre, then pad/crop to A's shape (centred)
            Bs = ndimage.zoom(grid_b, s, order=0) if s != 1.0 else grid_b
            Br = ndimage.rotate(Bs, ang, order=0, reshape=True, cval=UNKNOWN)
            canvas = np.full((H, W), UNKNOWN, np.uint8)
            h, w = Br.shape
            r0, c0 = (H - h) // 2, (W - w) // 2
            src_r0, src_c0 = max(0, -r0), max(0, -c0)
            dst_r0, dst_c0 = max(0, r0), max(0, c0)
            hh, ww = min(h - src_r0, H - dst_r0), min(w - src_c0, W - dst_c0)
            if hh <= 0 or ww <= 0:
                continue
            canvas[dst_r0:dst_r0 + hh, dst_c0:dst_c0 + ww] = Br[src_r0:src_r0 + hh, src_c0:src_c0 + ww]
            score, (dr, dc) = _xcorr_best(A, _mask(canvas, OCCUPIED))
            if score > best["score"]:
                best = {"score": score, "angle": ang, "scale": s, "shift": (dr, dc), "canvas": canvas}
    canvas = best.pop("canvas")
    dr, dc = best["shift"]
    aligned = np.full((H, W), UNKNOWN, np.uint8)
    # shift canvas by (dr, dc)
    rs, re_ = max(0, dr), min(H, H + dr); cs, ce = max(0, dc), min(W, W + dc)
    aligned[rs:re_, cs:ce] = canvas[rs - dr:re_ - dr, cs - dc:ce - dc]
    best["aligned"] = aligned
    return best


def diff_observations(belief: BeliefMap, aligned_b: np.ndarray, min_blob: int = 3) -> Tuple[Dict[str, List[int]], Dict]:
    """Cells where the second scan disagrees with the belief, as observation lists (json-key -> [values])."""
    obs: Dict[str, List[int]] = {}
    new_occ = (aligned_b == OCCUPIED) & (belief.grid == FREE)
    new_free = (aligned_b == FREE) & (belief.grid == OCCUPIED)
    # ignore tiny specks (reconstruction noise)
    for mask in (new_occ, new_free):
        lab, n = ndimage.label(mask)
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        for i, sz in enumerate(sizes, start=1):
            if sz < min_blob:
                mask[lab == i] = False
    for r, c in np.argwhere(new_occ):
        obs[json.dumps([int(r), int(c)])] = [OCCUPIED, OCCUPIED]
    for r, c in np.argwhere(new_free):
        obs[json.dumps([int(r), int(c)])] = [FREE, FREE]
    # also confirm cells both scans agree on (free/occupied) so the repair's consensus has support
    summary = {"new_occupied": int(new_occ.sum()), "new_free": int(new_free.sum()),
               "agree_free": int(((aligned_b == FREE) & (belief.grid == FREE)).sum()),
               "agree_occupied": int(((aligned_b == OCCUPIED) & (belief.grid == OCCUPIED)).sum())}
    return obs, summary


def rescan_plot(belief: BeliefMap, aligned_b: np.ndarray, reg: Dict, out_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ..viz import CMAP, NORM
    fig, axs = plt.subplots(1, 3, figsize=(15, 5))
    axs[0].imshow(belief.grid, cmap=CMAP, norm=NORM, interpolation="nearest"); axs[0].set_title("map from scan A")
    axs[1].imshow(aligned_b, cmap=CMAP, norm=NORM, interpolation="nearest")
    axs[1].set_title(f"scan B aligned to A (rot {reg['angle']}°, scale {reg['scale']}, shift {reg['shift']}, score {reg['score']:.2f})", fontsize=9)
    diff = np.zeros(belief.grid.shape + (3,), np.float32) + 0.94
    diff[(aligned_b == OCCUPIED) & (belief.grid == FREE)] = (0.86, 0.22, 0.27)   # new obstacle: red
    diff[(aligned_b == FREE) & (belief.grid == OCCUPIED)] = (0.18, 0.55, 0.34)   # obstacle gone: green
    diff[(belief.grid == UNKNOWN) & (aligned_b == UNKNOWN)] = (0.6, 0.63, 0.65)
    axs[2].imshow(diff, interpolation="nearest"); axs[2].set_title("difference: red = new obstacle, green = obstacle gone")
    for ax in axs:
        ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout(); fig.savefig(out_path, dpi=120); plt.close(fig)
    return out_path
