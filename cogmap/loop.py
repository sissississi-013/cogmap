"""The CogMap loop.

    scan -> belief v0 -> [eval] -> perturb world -> swarm fails -> repair -> belief v_{k+1} -> [eval] ...

Inner loop  = self-correcting map (failures drive repair until success recovers).
Outer loop  = self-improving swarm (volatility prior -> patrols find changes before tasks fail).
Everything is traced in Weave; each map version is a Weave Evaluation.
"""
from __future__ import annotations

import json
import os
import time
from typing import Callable, Dict, List, Optional

import weave

from .agents import Swarm, summarize, pool_observations, EpisodeResult
from .evals import evaluate_map, publish_leaderboard, weave_urls
from .repair import rule_repair, llm_propose_ops, validate_and_apply_ops, patrol_targets, search_targets, reflect
from .world import BeliefMap, TrueWorld, Cell


def _obs_json(pooled: Dict[Cell, List[int]]) -> Dict[str, List[int]]:
    return {json.dumps([int(c[0]), int(c[1])]): v for c, v in pooled.items()}


@weave.op
def run_swarm(belief_json: dict, world_json: dict, tasks: List[dict], n_agents: int = 8) -> dict:
    world = TrueWorld.from_json(world_json)
    belief = BeliefMap.from_json(belief_json)
    results = Swarm(world, n_agents=n_agents).run(belief, tasks)
    return {"summary": summarize(results), "results": [r.to_json() for r in results],
            "observations": _obs_json(pool_observations(results)),
            "paths": [[list(c) for c in r.path] for r in results]}


@weave.op
def run_patrols(belief_json: dict, world_json: dict, targets: List[List[int]], start: List[int]) -> dict:
    world = TrueWorld.from_json(world_json)
    belief = BeliefMap.from_json(belief_json)
    res = Swarm(world).patrol(belief, [tuple(t) for t in targets], tuple(start))
    return {"steps": res.steps, "collisions": res.collisions, "observations": _obs_json(pool_observations([res])),
            "failures": [f.to_json() for f in res.failures], "path": [list(c) for c in res.path]}


@weave.op
def repair_map(belief_json: dict, swarm_out: dict, use_llm: bool = True, extra_obs: Optional[dict] = None) -> dict:
    """One repair pass: rule repair, then (optionally) LLM scene-graph ops validated against observations."""
    obs = dict(swarm_out["observations"])
    if extra_obs:
        for k, v in extra_obs.items():
            obs.setdefault(k, []).extend(v)
    failures = [f for r in swarm_out["results"] for f in r["failures"]]
    rr = rule_repair(belief_json, swarm_out["results"], obs)
    out = {"rule_ops": rr["ops"], "rule_changed": rr["changed"], "llm": None}
    belief_json = rr["belief"]
    if use_llm and failures:
        removed = [o for o in rr["ops"] if o["op"] == "remove_object"]
        added = [o for o in rr["ops"] if o["op"] == "add_object"]
        try:
            prop = llm_propose_ops(belief_json, failures, removed, added, rule_ops=rr["ops"])
            va = validate_and_apply_ops(belief_json, prop.get("ops", []), obs)
            belief_json = va["belief"]
            out["llm"] = {"summary": prop.get("summary"), "applied": va["applied"], "rejected": va["rejected"]}
        except Exception as e:  # noqa: BLE001
            out["llm"] = {"error": str(e)}
    out["belief"] = belief_json
    return out


class CogMapLoop:
    def __init__(self, world: TrueWorld, belief: BeliefMap, tasks: List[dict], out_dir: str = "out",
                 use_llm: bool = True, use_patrols: bool = True, recover_threshold: float = 0.85,
                 max_repairs_per_round: int = 3, n_agents: int = 8):
        self.world, self.belief, self.tasks = world, belief, tasks
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.use_llm, self.use_patrols = use_llm, use_patrols
        self.recover_threshold = recover_threshold
        self.max_repairs_per_round = max_repairs_per_round
        self.n_agents = n_agents
        self.timeline: List[dict] = []      # every evaluated (map version, world state)
        self.frames: List[dict] = []        # for the animation: belief grid, true grid, paths, label
        self.eval_refs: List[str] = []
        self.patrol_start = tuple(tasks[0]["start"])

    def _eval(self, label: str, story: str = "", extra: Optional[dict] = None) -> dict:
        m = evaluate_map(self.belief, self.world, self.tasks, label, story)
        m.update(extra or {})
        if m.get("eval_ref"):
            self.eval_refs.append(m["eval_ref"])
        self.timeline.append(m)
        self.belief.save(os.path.join(self.out_dir, f"belief_v{self.belief.version}.json"))
        print(f"[eval] {label}: success={m['success_rate']:.2f} spl={m['spl']:.2f} collisions={m['collisions']:.0f}")
        return m

    def _recovered(self, m: dict) -> bool:
        b = getattr(self, "baseline", None) or {"success_rate": 1.0, "collisions": 0, "spl": 1.0}
        return (m["success_rate"] >= min(self.recover_threshold, b["success_rate"] - 0.05)
                and m["collisions"] <= max(0, 0.25 * b["collisions"])
                and m["spl"] >= 0.9 * b["spl"])

    @staticmethod
    def _better(m: dict, prev: dict) -> bool:
        return (m["success_rate"] > prev["success_rate"] + 1e-9 or m["collisions"] < prev["collisions"] - 1e-9
                or m["spl"] > prev["spl"] + 1e-9)

    def _snapshot(self, label: str, swarm_out: Optional[dict] = None, patrol_path=None):
        self.frames.append({"label": label, "version": self.belief.version,
                            "belief": self.belief.grid.tolist(), "true": self.world.grid.tolist(),
                            "objects": {k: v.to_json() for k, v in self.belief.objects.items()},
                            "volatility": self.belief.volatility.round(2).tolist(),
                            "paths": swarm_out["paths"] if swarm_out else [],
                            "failures": [f for r in swarm_out["results"] for f in r["failures"]] if swarm_out else [],
                            "patrol_path": patrol_path or []})

    @weave.op
    def run(self, perturbations: List[dict]) -> dict:
        t0 = time.time()
        base = self._eval("v0-initial", "Initial cognitive map from the scan.")
        self.baseline = base
        self._snapshot("v0 initial map")
        rounds = []
        for i, p in enumerate(perturbations, start=1):
            info = p["fn"](self.world, *p["args"])
            story = p.get("story", json.dumps(info))
            print(f"\n=== Round {i}: {story}")
            steps_to_recover = 0
            # --- outer loop: patrol high-volatility cells BEFORE running tasks
            extra_obs = None
            patrol_path = None
            if self.use_patrols and i > 1:
                targets = patrol_targets(self.belief.to_json())
                if targets:
                    pr = run_patrols(self.belief.to_json(), self.world.to_json(), targets, list(self.patrol_start))
                    steps_to_recover += pr["steps"]
                    extra_obs = pr["observations"]
                    patrol_path = pr["path"]
                    if pr["failures"]:
                        # patrol found a change: repair immediately, before any task fails
                        rep = repair_map(self.belief.to_json(), {"observations": {}, "results": [{"failures": pr["failures"]}]},
                                         use_llm=self.use_llm, extra_obs=extra_obs)
                        self.belief = BeliefMap.from_json(rep["belief"])
                        print(f"  patrol detected change at {len(pr['failures'])} cells -> pre-emptive repair -> v{self.belief.version}")
            # --- inner loop: tasks fail -> repair -> re-eval until recovered
            m = self._eval(f"v{self.belief.version}-after-change-{i}", story, {"round": i, "phase": "after_change"})
            swarm_out = run_swarm(self.belief.to_json(), self.world.to_json(), self.tasks, self.n_agents)
            steps_to_recover += swarm_out["summary"]["steps"]
            self._snapshot(f"round {i}: world changed (map v{self.belief.version})", swarm_out, patrol_path)
            n_rep = 0
            prev = None
            while not self._recovered(m) and n_rep < self.max_repairs_per_round and (prev is None or self._better(m, prev)):
                prev = m
                # active search: if a goal object went missing, sweep unobserved cells to find where it went
                missing = {f["goal"] for r in swarm_out["results"] for f in r["failures"] if f["kind"] == "goal_missing"}
                if missing:
                    observed = [json.loads(k) for k in swarm_out["observations"].keys()]
                    targets = search_targets(self.belief.to_json(), observed)
                    if targets:
                        sr = run_patrols(self.belief.to_json(), self.world.to_json(), targets, list(self.patrol_start))
                        steps_to_recover += sr["steps"]
                        extra_obs = dict(extra_obs or {})
                        for kk, vv in sr["observations"].items():
                            extra_obs.setdefault(kk, []).extend(vv)
                        print(f"  search sweep for missing {sorted(missing)}: {sr['steps']} steps, {len(sr['observations'])} cells observed")
                rep = repair_map(self.belief.to_json(), swarm_out, use_llm=self.use_llm, extra_obs=extra_obs)
                changed = rep["rule_changed"] or (rep["llm"] and rep["llm"].get("applied"))
                self.belief = BeliefMap.from_json(rep["belief"])
                n_rep += 1
                print(f"  repair #{n_rep}: rule ops={rep['rule_ops']} llm={ (rep['llm'] or {}).get('summary') }")
                if not changed:
                    print("  repair made no change; stopping this round")
                    break
                m = self._eval(f"v{self.belief.version}-repaired-{i}.{n_rep}", story, {"round": i, "phase": "repaired"})
                swarm_out = run_swarm(self.belief.to_json(), self.world.to_json(), self.tasks, self.n_agents)
                if m["success_rate"] < self.recover_threshold:
                    steps_to_recover += swarm_out["summary"]["steps"]
                self._snapshot(f"round {i}: repaired -> map v{self.belief.version}", swarm_out)
            rounds.append({"round": i, "story": story, "perturbation": info, "repairs": n_rep,
                           "steps_to_recover": steps_to_recover, "final_success": m["success_rate"],
                           "map_version": self.belief.version})
            print(f"  round {i} done: success={m['success_rate']:.2f} steps_to_recover={steps_to_recover} repairs={n_rep}")
        lb = publish_leaderboard(self.eval_refs)
        changelog = reflect(self.belief.changelog, [r["story"] for r in rounds], self.timeline)
        with open(os.path.join(self.out_dir, "map_changelog.md"), "w") as f:
            f.write(changelog)
        result = {"timeline": self.timeline, "rounds": rounds, "leaderboard": lb, "weave": weave_urls(),
                  "n_tasks": len(self.tasks), "elapsed_s": round(time.time() - t0, 1)}
        with open(os.path.join(self.out_dir, "loop_result.json"), "w") as f:
            json.dump(result, f, indent=1)
        with open(os.path.join(self.out_dir, "frames.json"), "w") as f:
            json.dump(self.frames, f)
        return result
