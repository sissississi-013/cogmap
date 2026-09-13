import os
import numpy as np
from scipy import ndimage

os.environ.setdefault("WEAVE_DISABLED", "true")

from cogmap.world import make_synthetic_apartment, BeliefMap, UNKNOWN, FREE, OCCUPIED
from cogmap.scan.rescan import register, diff_observations


def test_register_recovers_rotation_and_shift():
    w = make_synthetic_apartment(); a = BeliefMap.from_world(w).grid
    # pad into a square canvas with unknown margin, rotate by 20 deg and shift, then register back
    H = W = 90
    canvas = np.full((H, W), UNKNOWN, np.uint8); canvas[25:55, 15:65] = a
    b = ndimage.rotate(canvas, 20, order=0, reshape=False, cval=UNKNOWN)
    b = np.roll(b, (3, -4), axis=(0, 1))
    reg = register(canvas, b, angles=range(0, 360, 2), scales=(1.0,))
    assert reg["score"] > 0.6
    assert reg["angle"] in (338, 340, 342)          # inverse of +20 deg (mod 360), within the 2-deg search step
    aligned = reg["aligned"]
    agree = ((aligned == OCCUPIED) & (canvas == OCCUPIED)).sum() / max(1, (canvas == OCCUPIED).sum())
    assert agree > 0.6


def test_diff_observations_reports_moved_object():
    w = make_synthetic_apartment(); a = BeliefMap.from_world(w)
    b = a.grid.copy()
    for c in w.objects["couch"].cells:            # couch gone from its spot ...
        b[c] = FREE
    b[20:22, 30:38] = OCCUPIED                      # ... and a new block in the hallway
    obs, summ = diff_observations(a, b, min_blob=3)
    assert summ["new_free"] >= 16 and summ["new_occupied"] >= 16
    vals = set(v for vs in obs.values() for v in vs)
    assert vals == {FREE, OCCUPIED}
