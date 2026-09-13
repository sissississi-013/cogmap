"""Export a BeliefMap as the ROS 2 Nav2 map_server artifact (map.pgm + map.yaml) + waypoints.json.

This is the file pair that slam_toolbox/Nav2 stacks on Unitree Go2/G1 load today.
"""
from __future__ import annotations

import json
import os
from typing import Dict

import numpy as np

from ..world import BeliefMap, UNKNOWN, FREE, OCCUPIED


def export_nav2(belief: BeliefMap, out_dir: str, resolution: float = 0.15, origin_xy=(0.0, 0.0), name: str = "map") -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    g = belief.grid
    img = np.full(g.shape, 205, np.uint8)      # unknown
    img[g == FREE] = 254
    img[g == OCCUPIED] = 0
    img = np.flipud(img)                        # map_server: bottom row = origin
    pgm = os.path.join(out_dir, f"{name}.pgm")
    with open(pgm, "wb") as f:
        f.write(f"P5\n# CogMap v{belief.version}\n{g.shape[1]} {g.shape[0]}\n255\n".encode())
        f.write(img.tobytes())
    yaml_path = os.path.join(out_dir, f"{name}.yaml")
    with open(yaml_path, "w") as f:
        f.write(f"image: {name}.pgm\nmode: trinary\nresolution: {resolution}\norigin: [{origin_xy[0]:.3f}, {origin_xy[1]:.3f}, 0.0]\n"
                f"negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n")
    # waypoints: the free cell adjacent to each object's footprint (where a robot would stop), in map metres
    wps = {}
    for nm, o in belief.objects.items():
        best = None
        for (r, c) in o.cells:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nb = (r + dr, c + dc)
                if belief.in_bounds(nb) and belief.grid[nb] == FREE and nb not in o.cells:
                    best = nb; break
            if best:
                break
        cell = best or o.anchor
        wps[nm] = {"x": round(origin_xy[0] + (cell[1] + 0.5) * resolution, 3),
                   "y": round(origin_xy[1] + (cell[0] + 0.5) * resolution, 3), "yaw": 0.0,
                   "cell": [int(cell[0]), int(cell[1])], "kind": o.kind, "confidence": o.confidence}
    wp_path = os.path.join(out_dir, "waypoints.json")
    with open(wp_path, "w") as f:
        json.dump({"frame_id": "map", "map_version": belief.version, "waypoints": wps}, f, indent=1)
    return {"pgm": pgm, "yaml": yaml_path, "waypoints": wp_path}
