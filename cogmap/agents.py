"""Navigation agents and the swarm runner.

Agents plan on the *belief* map and execute on the *true* world with a local
sensor.  Every mismatch between expectation and observation is recorded as a
FailureEvent; all observations are pooled so the repair step can fix the map.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from .world import BeliefMap, TrueWorld, Cell, FREE, OCCUPIED, UNKNOWN

NEIGH4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def astar(passable, start: Cell, goals: Set[Cell], shape, unknown_cost=None, max_expansions: int = 200_000) -> Optional[List[Cell]]:
    """4-connected A* to any cell in `goals`. `passable(cell)->bool`; `unknown_cost(cell)->float extra`."""
    if start in goals:
        return [start]
    H, W = shape

    def h(c):
        return min(abs(c[0] - g[0]) + abs(c[1] - g[1]) for g in goals)

    openq = [(h(start), 0.0, start)]
    came: Dict[Cell, Cell] = {}
    gsc = {start: 0.0}
    closed = set()
    n = 0
    while openq and n < max_expansions:
        _, g, cur = heapq.heappop(openq)
        if cur in closed:
            continue
        closed.add(cur)
        n += 1
        if cur in goals:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1]
        for dr, dc in NEIGH4:
            nb = (cur[0] + dr, cur[1] + dc)
            if not (0 <= nb[0] < H and 0 <= nb[1] < W) or not passable(nb) or nb in closed:
                continue
            ng = g + 1.0 + (unknown_cost(nb) if unknown_cost else 0.0)
            if ng < gsc.get(nb, 1e18):
                gsc[nb] = ng
                came[nb] = cur
                heapq.heappush(openq, (ng + h(nb), ng, nb))
    return None


def goal_cells_for(belief: BeliefMap, goal: str) -> Set[Cell]:
    """Free cells adjacent to the believed footprint of `goal`."""
    cells = belief.object_cells(goal)
    adj = set()
    for r, c in cells:
        for dr, dc in NEIGH4:
            nb = (r + dr, c + dc)
            if belief.in_bounds(nb) and nb not in cells and belief.grid[nb] != OCCUPIED:
                adj.add(nb)
    return adj


@dataclass
class FailureEvent:
    kind: str            # "blocked" | "unexpected_free" | "goal_missing" | "no_path" | "timeout"
    cell: Cell
    expected: int
    observed: int
    agent_id: str
    step: int
    goal: str

    def to_json(self):
        return {"kind": self.kind, "cell": list(self.cell), "expected": self.expected,
                "observed": self.observed, "agent": self.agent_id, "step": self.step, "goal": self.goal}


@dataclass
class EpisodeResult:
    task_id: str
    agent_id: str
    goal: str
    success: bool
    steps: int
    optimal_len: int
    collisions: int
    replans: int
    failures: List[FailureEvent] = field(default_factory=list)
    observations: Dict[Cell, int] = field(default_factory=dict)
    path: List[Cell] = field(default_factory=list)

    @property
    def spl(self) -> float:
        if not self.success or self.steps == 0:
            return 0.0
        return float(self.optimal_len) / max(self.steps, self.optimal_len)

    def to_json(self):
        return {"task_id": self.task_id, "agent": self.agent_id, "goal": self.goal, "success": self.success,
                "steps": self.steps, "optimal_len": self.optimal_len, "spl": round(self.spl, 3),
                "collisions": self.collisions, "replans": self.replans,
                "failures": [f.to_json() for f in self.failures], "path_len": len(self.path)}


class NavAgent:
    """Plans on a private copy of the belief, executes on the true world."""

    def __init__(self, agent_id: str, belief: BeliefMap, world: TrueWorld, max_steps: int = 400, max_replans: int = 25,
                 sensor_radius: int = 1, budget_factor: float = 1.5, budget_slack: int = 10):
        self.id = agent_id
        self.belief = belief.copy()      # private working copy; the shared belief stays frozen
        self.world = world
        self.max_steps = max_steps
        self.max_replans = max_replans
        self.sensor_radius = sensor_radius
        self.budget_factor = budget_factor
        self.budget_slack = budget_slack

    def _unknown_cost(self, cell: Cell) -> float:
        return 2.0 if self.belief.grid[cell] == UNKNOWN else 0.0

    def run(self, task: dict) -> EpisodeResult:
        start = tuple(task["start"])
        goal = task["goal"]
        res = EpisodeResult(task["id"], self.id, goal, False, 0, 0, 0, 0)
        goals = goal_cells_for(self.belief, goal)
        if not goals:
            res.failures.append(FailureEvent("goal_missing", start, OCCUPIED, FREE, self.id, 0, goal))
            return res
        # optimal path on the true world (for SPL)
        true_goals = goal_cells_for(BeliefMap.from_world(self.world), goal) if goal in self.world.objects else set()
        opt = astar(self.world.is_free, start, true_goals, self.world.shape) if true_goals else None
        res.optimal_len = len(opt) - 1 if opt else 0
        # realistic mission budget: a robot that takes >1.5x the optimal time has failed the task
        budget = min(self.max_steps, int(self.budget_factor * res.optimal_len) + self.budget_slack) if res.optimal_len else self.max_steps

        pos = start
        res.path = [pos]
        self._observe(pos, res)
        path = astar(self.belief.passable, pos, goals, self.belief.shape, self._unknown_cost)
        if path is None:
            res.failures.append(FailureEvent("no_path", pos, FREE, OCCUPIED, self.id, 0, goal))
            return res
        idx = 1
        while res.steps < budget:
            if pos in goals:
                # verify the goal object is really there (sensor sees its footprint)
                seen = self.world.sense(pos, self.sensor_radius)
                foot = self.belief.object_cells(goal)
                if any(seen.get(c) == OCCUPIED for c in foot):
                    res.success = True
                    return res
                res.failures.append(FailureEvent("goal_missing", pos, OCCUPIED, FREE, self.id, res.steps, goal))
                # mark believed footprint free in private copy and try to find it elsewhere: give up (map is wrong)
                return res
            if idx >= len(path):
                break
            nxt = path[idx]
            seen = self._observe(pos, res)
            if seen.get(nxt, FREE) != FREE:
                res.collisions += 1
                res.failures.append(FailureEvent("blocked", nxt, int(self.belief.grid[nxt]), int(seen[nxt]), self.id, res.steps, goal))
                res.replans += 1
                if res.replans > self.max_replans:
                    break
                goals = goal_cells_for(self.belief, goal)
                path = astar(self.belief.passable, pos, goals, self.belief.shape, self._unknown_cost)
                if path is None:
                    res.failures.append(FailureEvent("no_path", pos, FREE, OCCUPIED, self.id, res.steps, goal))
                    return res
                idx = 1
                continue
            pos = nxt
            idx += 1
            res.steps += 1
            res.path.append(pos)
        if not res.success:
            res.failures.append(FailureEvent("timeout", pos, FREE, FREE, self.id, res.steps, goal))
        return res

    def _observe(self, pos: Cell, res: EpisodeResult) -> Dict[Cell, int]:
        seen = self.world.sense(pos, self.sensor_radius)
        for cell, val in seen.items():
            res.observations[cell] = val
            bval = int(self.belief.grid[cell])
            if bval != val:
                if bval == FREE and val == OCCUPIED:
                    pass  # recorded as "blocked" only when it affects the path; still update private belief
                elif bval == OCCUPIED and val == FREE:
                    res.failures.append(FailureEvent("unexpected_free", cell, bval, val, self.id, res.steps, res.goal))
                self.belief.set_cell(cell, val, 0.95)
        return seen


class Swarm:
    def __init__(self, world: TrueWorld, n_agents: int = 8, max_steps: int = 400, budget_factor: float = 1.5):
        self.world = world
        self.n_agents = n_agents
        self.max_steps = max_steps
        self.budget_factor = budget_factor

    def run(self, belief: BeliefMap, tasks: List[dict]) -> List[EpisodeResult]:
        results = []
        for i, task in enumerate(tasks):
            agent = NavAgent(f"a{i % self.n_agents}", belief, self.world, max_steps=self.max_steps,
                             budget_factor=self.budget_factor)
            results.append(agent.run(task))
        return results

    def patrol(self, belief: BeliefMap, targets: List[Cell], start: Cell, max_steps: int = 300) -> EpisodeResult:
        """Send one patrol agent through a list of target cells (verification sweep)."""
        agent = NavAgent("patrol", belief, self.world, max_steps=max_steps)
        res = EpisodeResult("patrol", "patrol", "patrol", True, 0, 0, 0, 0)
        pos = start
        res.path = [pos]
        for t in targets:
            goals = {t} if agent.belief.grid[t] != OCCUPIED else {
                (t[0] + dr, t[1] + dc) for dr, dc in NEIGH4 if agent.belief.passable((t[0] + dr, t[1] + dc))}
            if not goals:
                continue
            path = astar(agent.belief.passable, pos, goals, agent.belief.shape, agent._unknown_cost)
            if path is None:
                continue
            for nxt in path[1:]:
                seen = agent._observe(pos, res)
                if seen.get(nxt, FREE) != FREE:
                    res.collisions += 1
                    res.failures.append(FailureEvent("blocked", nxt, int(belief.grid[nxt]), int(seen[nxt]), "patrol", res.steps, "patrol"))
                    break
                pos = nxt
                res.steps += 1
                res.path.append(pos)
                if res.steps >= max_steps:
                    break
            agent._observe(pos, res)
            if res.steps >= max_steps:
                break
        return res


def summarize(results: List[EpisodeResult]) -> dict:
    n = len(results)
    if n == 0:
        return {"n": 0, "success_rate": 0.0, "spl": 0.0, "collisions": 0, "steps": 0}
    return {"n": n,
            "success_rate": sum(r.success for r in results) / n,
            "spl": float(np.mean([r.spl for r in results])),
            "collisions": int(sum(r.collisions for r in results)),
            "steps": int(sum(r.steps for r in results)),
            "failures": int(sum(len(r.failures) for r in results))}


def pool_observations(results: List[EpisodeResult]) -> Dict[Cell, List[int]]:
    pooled: Dict[Cell, List[int]] = {}
    for r in results:
        for cell, val in r.observations.items():
            pooled.setdefault(cell, []).append(val)
    return pooled
