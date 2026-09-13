import os
import numpy as np

os.environ.setdefault("WEAVE_DISABLED", "true")

from cogmap.world import make_synthetic_apartment, BeliefMap, UNKNOWN, FREE
from cogmap.repair import frontier_targets, coverage


def test_frontier_targets_border_unknown_space():
    w = make_synthetic_apartment(); b = BeliefMap.from_world(w)
    assert frontier_targets(b.to_json()) == []          # fully known map has no frontier
    b.grid[15:29, 26:49] = UNKNOWN                      # forget the hallway
    t = frontier_targets(b.to_json(), n=6)
    assert 1 <= len(t) <= 6
    for r, c in t:
        assert b.grid[r, c] == FREE
        nb = b.grid[max(0, r - 1):r + 2, max(0, c - 1):c + 2]
        assert (nb == UNKNOWN).any()                    # every target touches unknown cells
    cov = coverage(b.to_json())
    assert cov["unknown_cells"] == 14 * 23 and cov["known_cells"] + cov["unknown_cells"] == 30 * 50
