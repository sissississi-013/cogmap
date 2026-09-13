import numpy as np

from cogmap.world import make_synthetic_apartment, default_tasks, BeliefMap, TrueWorld, WorldObject, FREE, OCCUPIED
from cogmap.agents import astar, Swarm, summarize, goal_cells_for


def test_apartment_has_objects_and_doors():
    w = make_synthetic_apartment()
    assert len(w.objects) >= 10
    assert all((w.grid[c] == OCCUPIED) for o in w.objects.values() for c in o.cells)
    for cells in w.doors.values():
        assert all(w.grid[c] == FREE for c in cells)


def test_astar_finds_path_through_door():
    w = make_synthetic_apartment()
    p = astar(w.is_free, (2, 2), {(27, 44)}, w.shape)
    assert p is not None and p[0] == (2, 2) and p[-1] == (27, 44)


def test_perfect_belief_gives_high_success():
    w = make_synthetic_apartment()
    b = BeliefMap.from_world(w)
    tasks = default_tasks(w, 12)
    res = Swarm(w).run(b, tasks)
    s = summarize(res)
    assert s["success_rate"] >= 0.9, s


def test_moved_object_causes_failures():
    w = make_synthetic_apartment()
    b = BeliefMap.from_world(w)
    tasks = default_tasks(w, 12)
    # block the living->bedroom doorway with the coffee table
    w.move_object("coffee_table", (6, 25))
    res = Swarm(w).run(b, tasks)
    kinds = {f.kind for r in res for f in r.failures}
    assert "blocked" in kinds or "goal_missing" in kinds
    s = summarize(res)
    assert s["collisions"] > 0 or s["success_rate"] < 1.0


def test_world_json_roundtrip():
    w = make_synthetic_apartment()
    w2 = TrueWorld.from_json(w.to_json())
    assert np.array_equal(w.grid, w2.grid)
    b = BeliefMap.from_world(w)
    b2 = BeliefMap.from_json(b.to_json())
    assert np.array_equal(b.grid, b2.grid) and b2.objects.keys() == b.objects.keys()
