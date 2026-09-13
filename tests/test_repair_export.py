import json
import os

import numpy as np

os.environ.setdefault("WEAVE_DISABLED", "true")

from cogmap.world import make_synthetic_apartment, default_tasks, BeliefMap, relocate_object, block_door, FREE, OCCUPIED
from cogmap.agents import Swarm, pool_observations
from cogmap.repair import rule_repair, validate_and_apply_ops, patrol_targets, search_targets
from cogmap.scan.export_nav2 import export_nav2


def _obs_json(pooled):
    return {json.dumps([int(c[0]), int(c[1])]): v for c, v in pooled.items()}


def test_rule_repair_finds_moved_object_and_renames():
    w = make_synthetic_apartment(); b = BeliefMap.from_world(w); tasks = default_tasks(w, 16)
    relocate_object(w, "couch", (24, 40))
    res = Swarm(w).run(b, tasks)
    obs = _obs_json(pool_observations(res))
    # add a sweep so the new footprint is observed
    targets = search_targets(b.to_json(), [json.loads(k) for k in obs])
    sweep = Swarm(w).patrol(b, [tuple(t) for t in targets], tuple(tasks[0]["start"]))
    for k, v in _obs_json(pool_observations([sweep])).items():
        obs.setdefault(k, []).extend(v)
    out = rule_repair(b.to_json(), [r.to_json() for r in res], obs)
    ops = {o["op"] for o in out["ops"]}
    assert "remove_object" in ops and "add_object" in ops and "rename" in ops, out["ops"]
    nb = BeliefMap.from_json(out["belief"])
    assert "couch" in nb.objects and abs(nb.objects["couch"].anchor[0] - 24) <= 2
    assert nb.version == 1 and nb.volatility.max() > 0


def test_rule_repair_marks_blocked_door():
    w = make_synthetic_apartment(); b = BeliefMap.from_world(w); tasks = default_tasks(w, 16)
    block_door(w, "door_living_bedroom", "coffee_table")
    res = Swarm(w).run(b, tasks)
    out = rule_repair(b.to_json(), [r.to_json() for r in res], _obs_json(pool_observations(res)))
    nb = BeliefMap.from_json(out["belief"])
    assert nb.grid[6, 25] == OCCUPIED or nb.grid[7, 25] == OCCUPIED
    assert any(o["op"] == "add_object" for o in out["ops"])


def test_validate_rejects_ops_contradicting_observations():
    w = make_synthetic_apartment(); b = BeliefMap.from_world(w)
    obs = {json.dumps([20, 30]): [FREE, FREE], json.dumps([20, 31]): [FREE]}
    ops = [{"op": "add", "name": "ghost", "cells": [[20, 30], [20, 31]]},          # observed free -> reject
           {"op": "relocate", "name": "plant", "to": [2000, 2000]},                 # out of bounds -> reject
           {"op": "remove", "name": "shoe_rack"},                                   # fine
           {"op": "rename", "name": "laundry_basket", "new_name": "hamper"}]        # fine
    out = validate_and_apply_ops(b.to_json(), ops, obs)
    assert len(out["rejected"]) == 2 and len(out["applied"]) == 2
    nb = BeliefMap.from_json(out["belief"])
    assert "shoe_rack" not in nb.objects and "hamper" in nb.objects and "ghost" not in nb.objects


def test_patrol_targets_follow_volatility():
    w = make_synthetic_apartment(); b = BeliefMap.from_world(w)
    b.bump("test", [(6, 25), (7, 25)])
    t = patrol_targets(b.to_json(), n=3)
    assert t and abs(t[0][0] - 6.5) <= 1 and t[0][1] == 25


def test_export_nav2_roundtrip(tmp_path):
    w = make_synthetic_apartment(); b = BeliefMap.from_world(w)
    out = export_nav2(b, str(tmp_path), resolution=0.1, origin_xy=(-1.0, -2.0))
    with open(out["pgm"], "rb") as f:
        header = f.readline(); comment = f.readline(); dims = f.readline(); maxv = f.readline(); data = f.read()
    assert header.strip() == b"P5" and dims.strip() == b"50 30" and maxv.strip() == b"255"
    img = np.frombuffer(data, np.uint8).reshape(30, 50)
    assert (img == 0).sum() == (w.grid == OCCUPIED).sum() and (img == 254).sum() == (w.grid == FREE).sum()
    yaml = open(out["yaml"]).read()
    assert "resolution: 0.1" in yaml and "origin: [-1.000, -2.000, 0.0]" in yaml
    wps = json.load(open(out["waypoints"]))["waypoints"]
    assert set(wps) == set(w.objects) and all("x" in v and "y" in v for v in wps.values())
