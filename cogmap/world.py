"""World representations for CogMap.

Grid cell values (shared with the VGGT scan pipeline):
    UNKNOWN = 0, FREE = 1, OCCUPIED = 2
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

import numpy as np

UNKNOWN, FREE, OCCUPIED = 0, 1, 2
Cell = Tuple[int, int]


@dataclass
class WorldObject:
    name: str
    cells: List[Cell]
    kind: str = "furniture"
    confidence: float = 1.0

    @property
    def anchor(self) -> Cell:
        rs = [c[0] for c in self.cells]
        cs = [c[1] for c in self.cells]
        return (int(round(np.mean(rs))), int(round(np.mean(cs))))

    def to_json(self) -> dict:
        return {"name": self.name, "cells": [list(c) for c in self.cells],
                "kind": self.kind, "confidence": self.confidence, "anchor": list(self.anchor)}

    @staticmethod
    def from_json(d: dict) -> "WorldObject":
        return WorldObject(d["name"], [tuple(c) for c in d["cells"]], d.get("kind", "furniture"),
                           float(d.get("confidence", 1.0)))


class TrueWorld:
    """Ground-truth environment the agents actually move in."""

    def __init__(self, grid: np.ndarray, objects: Optional[Dict[str, WorldObject]] = None, name: str = "world"):
        self.grid = grid.astype(np.uint8)
        self.objects: Dict[str, WorldObject] = objects or {}
        self.name = name
        self.static = self.grid.copy()  # walls only (before objects are stamped)
        for o in self.objects.values():
            self._stamp(o, OCCUPIED)

    @property
    def shape(self):
        return self.grid.shape

    def _stamp(self, obj: WorldObject, value: int):
        for r, c in obj.cells:
            if 0 <= r < self.grid.shape[0] and 0 <= c < self.grid.shape[1]:
                self.grid[r, c] = value

    def in_bounds(self, cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < self.grid.shape[0] and 0 <= c < self.grid.shape[1]

    def is_free(self, cell: Cell) -> bool:
        return self.in_bounds(cell) and self.grid[cell] == FREE

    def sense(self, cell: Cell, radius: int = 1) -> Dict[Cell, int]:
        """Local sensor: returns true values of the (2r+1)^2 neighbourhood."""
        r0, c0 = cell
        out = {}
        for r in range(r0 - radius, r0 + radius + 1):
            for c in range(c0 - radius, c0 + radius + 1):
                if self.in_bounds((r, c)):
                    out[(r, c)] = int(self.grid[r, c])
        return out

    # ---- perturbations -------------------------------------------------
    def move_object(self, name: str, new_anchor: Cell) -> WorldObject:
        obj = self.objects[name]
        self._stamp(obj, FREE)
        # restore any static wall under the old footprint
        for r, c in obj.cells:
            self.grid[r, c] = self.static[r, c]
        ar, ac = obj.anchor
        dr, dc = new_anchor[0] - ar, new_anchor[1] - ac
        obj.cells = [(r + dr, c + dc) for r, c in obj.cells]
        self._stamp(obj, OCCUPIED)
        return obj

    def add_object(self, obj: WorldObject):
        self.objects[obj.name] = obj
        self._stamp(obj, OCCUPIED)

    def remove_object(self, name: str):
        obj = self.objects.pop(name)
        for r, c in obj.cells:
            self.grid[r, c] = self.static[r, c]

    def to_json(self) -> dict:
        return {"name": self.name, "grid": self.grid.tolist(), "static": self.static.tolist(),
                "objects": {k: v.to_json() for k, v in self.objects.items()}}

    @staticmethod
    def from_json(d: dict) -> "TrueWorld":
        w = TrueWorld(np.array(d["static"], dtype=np.uint8), name=d.get("name", "world"))
        for k, v in d["objects"].items():
            w.add_object(WorldObject.from_json(v))
        return w


class BeliefMap:
    """The agents' cognitive map: grid + confidence + object graph + volatility prior."""

    def __init__(self, grid: np.ndarray, objects: Optional[Dict[str, WorldObject]] = None,
                 confidence: Optional[np.ndarray] = None, version: int = 0, name: str = "belief"):
        self.grid = grid.astype(np.uint8)
        self.objects: Dict[str, WorldObject] = objects or {}
        self.confidence = confidence if confidence is not None else np.where(self.grid == UNKNOWN, 0.0, 0.9)
        self.volatility = np.zeros(self.grid.shape, dtype=np.float32)
        self.version = version
        self.name = name
        self.changelog: List[dict] = []

    @property
    def shape(self):
        return self.grid.shape

    def copy(self) -> "BeliefMap":
        b = BeliefMap(self.grid.copy(), {k: copy.deepcopy(v) for k, v in self.objects.items()},
                      self.confidence.copy(), self.version, self.name)
        b.volatility = self.volatility.copy()
        b.changelog = list(self.changelog)
        return b

    def in_bounds(self, cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < self.grid.shape[0] and 0 <= c < self.grid.shape[1]

    def passable(self, cell: Cell) -> bool:
        return self.in_bounds(cell) and self.grid[cell] != OCCUPIED

    def object_cells(self, name: str) -> Set[Cell]:
        return set(self.objects[name].cells) if name in self.objects else set()

    def stamp_object(self, obj: WorldObject, value: int = OCCUPIED, conf: float = 0.8):
        for cell in obj.cells:
            if self.in_bounds(cell):
                self.grid[cell] = value
                self.confidence[cell] = conf

    def set_cell(self, cell: Cell, value: int, conf: float):
        if self.in_bounds(cell):
            self.grid[cell] = value
            self.confidence[cell] = conf

    def bump(self, note: str, changed_cells: Iterable[Cell]):
        changed = list(changed_cells)
        self.version += 1
        self.volatility *= 0.85
        for cell in changed:
            if self.in_bounds(cell):
                self.volatility[cell] = min(1.0, self.volatility[cell] + 0.5)
        self.changelog.append({"version": self.version, "note": note, "n_changed": len(changed)})

    def summary(self) -> str:
        n_unknown = int((self.grid == UNKNOWN).sum())
        return (f"belief v{self.version}: {self.grid.shape[0]}x{self.grid.shape[1]} cells, "
                f"{n_unknown} unknown, {len(self.objects)} objects: "
                + ", ".join(f"{k}@{v.anchor}" for k, v in self.objects.items()))

    def to_json(self) -> dict:
        return {"name": self.name, "version": self.version, "grid": self.grid.tolist(),
                "confidence": np.round(self.confidence, 3).tolist(),
                "volatility": np.round(self.volatility, 3).tolist(),
                "objects": {k: v.to_json() for k, v in self.objects.items()},
                "changelog": self.changelog}

    @staticmethod
    def from_json(d: dict) -> "BeliefMap":
        b = BeliefMap(np.array(d["grid"], dtype=np.uint8),
                      {k: WorldObject.from_json(v) for k, v in d["objects"].items()},
                      np.array(d["confidence"], dtype=np.float32), int(d.get("version", 0)), d.get("name", "belief"))
        if "volatility" in d:
            b.volatility = np.array(d["volatility"], dtype=np.float32)
        b.changelog = list(d.get("changelog", []))
        return b

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_json(), f)

    @staticmethod
    def load(path: str) -> "BeliefMap":
        with open(path) as f:
            return BeliefMap.from_json(json.load(f))

    @staticmethod
    def from_world(world: TrueWorld, name: str = "belief") -> "BeliefMap":
        """Perfect initial belief (as if the scan were exact)."""
        return BeliefMap(world.grid.copy(), {k: copy.deepcopy(v) for k, v in world.objects.items()}, name=name)


# ---------------------------------------------------------------------------
# Synthetic apartment
# ---------------------------------------------------------------------------

def _rect(r0, c0, r1, c1) -> List[Cell]:
    return [(r, c) for r in range(r0, r1) for c in range(c0, c1)]


def make_synthetic_apartment(seed: int = 0) -> TrueWorld:
    """A 30x50 apartment: living room, bedroom, kitchen, hallway; doorways; furniture.

    Layout (rows x cols):
        rows 1..13  : living room (cols 1..24) | bedroom (cols 26..48)
        rows 15..28 : kitchen (cols 1..20)     | hallway (cols 22..48)
    Doorways connect rooms through the wall lines at row 14 and col 25.
    """
    H, W = 30, 50
    g = np.full((H, W), FREE, dtype=np.uint8)
    g[0, :] = OCCUPIED; g[-1, :] = OCCUPIED; g[:, 0] = OCCUPIED; g[:, -1] = OCCUPIED
    g[14, :] = OCCUPIED           # horizontal wall
    g[:, 25] = OCCUPIED           # vertical wall
    # doorways (2 cells wide)
    doors = {"door_living_bedroom": [(6, 25), (7, 25)],
             "door_living_kitchen": [(14, 10), (14, 11)],
             "door_bedroom_hall": [(14, 36), (14, 37)],
             "door_kitchen_hall": [(21, 25), (22, 25)]}
    for cells in doors.values():
        for cell in cells:
            g[cell] = FREE
    w = TrueWorld(g, name=f"synthetic_apartment_{seed}")
    rng = np.random.default_rng(seed)
    objs = [
        WorldObject("couch", _rect(3, 4, 5, 12)),
        WorldObject("coffee_table", _rect(7, 6, 9, 10)),
        WorldObject("tv_stand", _rect(11, 4, 12, 12)),
        WorldObject("bookshelf", _rect(2, 20, 12, 22)),
        WorldObject("bed", _rect(3, 30, 9, 38)),
        WorldObject("wardrobe", _rect(2, 44, 10, 46)),
        WorldObject("desk", _rect(11, 40, 12, 47)),
        WorldObject("dining_table", _rect(18, 6, 22, 12)),
        WorldObject("fridge", _rect(26, 2, 28, 4)),
        WorldObject("kitchen_island", _rect(24, 12, 26, 18)),
        WorldObject("plant", _rect(26, 46, 28, 48)),
        WorldObject("shoe_rack", _rect(16, 44, 17, 48)),
        WorldObject("laundry_basket", _rect(26, 28, 28, 30)),
    ]
    for o in objs:
        w.add_object(o)
    w.doors = doors  # type: ignore[attr-defined]
    return w


def default_tasks(world: TrueWorld, n: int = 12, seed: int = 0) -> List[dict]:
    """Fixed evaluation task set: (start cell, goal object)."""
    rng = np.random.default_rng(seed)
    free = np.argwhere(world.grid == FREE)
    names = list(world.objects.keys())
    tasks = []
    tries = 0
    while len(tasks) < n and tries < 10_000:
        tries += 1
        s = tuple(int(x) for x in free[rng.integers(len(free))])
        goal = names[rng.integers(len(names))]
        anchor = world.objects[goal].anchor
        if abs(s[0] - anchor[0]) + abs(s[1] - anchor[1]) < 12:
            continue
        tasks.append({"id": f"t{len(tasks)}", "start": list(s), "goal": goal})
    return tasks


# ---------------------------------------------------------------------------
# Perturbations (what "the world changed" means)
# ---------------------------------------------------------------------------

def block_door(world: TrueWorld, door_name: str, obj_name: str) -> dict:
    """Move `obj_name` so its footprint covers the doorway `door_name`."""
    door = world.doors[door_name]  # type: ignore[attr-defined]
    obj = world.objects[obj_name]
    rs = [c[0] for c in door]; cs = [c[1] for c in door]
    target = (int(round(np.mean(rs))), int(round(np.mean(cs))))
    old = obj.anchor
    world.move_object(obj_name, target)
    for cell in door:  # thin objects: make sure the whole doorway is covered
        if cell not in obj.cells:
            obj.cells.append(cell)
            world.grid[cell] = OCCUPIED
    return {"kind": "block_door", "object": obj_name, "door": door_name, "from": list(old), "to": list(obj.anchor)}


def relocate_object(world: TrueWorld, obj_name: str, new_anchor: Cell) -> dict:
    old = world.objects[obj_name].anchor
    world.move_object(obj_name, new_anchor)
    return {"kind": "relocate", "object": obj_name, "from": list(old), "to": list(new_anchor)}


def scripted_perturbations(world: TrueWorld) -> List[dict]:
    """Four rounds of scripted changes for the synthetic apartment demo (world stays connected)."""
    return [
        {"fn": block_door, "args": ["door_living_bedroom", "coffee_table"],
         "story": "Someone dragged the coffee table into the living-room/bedroom doorway."},
        {"fn": relocate_object, "args": ["couch", (24, 40)],
         "story": "The couch was moved from the living room into the hallway."},
        {"fn": relocate_object, "args": ["coffee_table", (8, 8)],
         "story": "The coffee table went back to the living room: the doorway is open again (stale obstacle in the map)."},
        {"fn": block_door, "args": ["door_bedroom_hall", "laundry_basket"],
         "story": "A laundry basket now blocks the bedroom/hallway doorway."},
    ]
