"""Weave evaluations: one Evaluation run per map version on a fixed task set."""
from __future__ import annotations

import asyncio
from typing import List, Optional

import weave

from .agents import NavAgent, EpisodeResult
from .world import BeliefMap, TrueWorld


class MapNavModel(weave.Model):
    """A frozen map version + the world it is evaluated in."""
    map_name: str
    version: int
    belief_json: dict
    world_json: dict
    budget_factor: float = 1.5

    @weave.op
    def predict(self, id: str, start: list, goal: str) -> dict:
        world = TrueWorld.from_json(self.world_json)
        belief = BeliefMap.from_json(self.belief_json)
        agent = NavAgent(f"eval-{id}", belief, world, budget_factor=self.budget_factor)
        res = agent.run({"id": id, "start": start, "goal": goal})
        return res.to_json()


@weave.op
def success(output: dict) -> float:
    return 1.0 if output["success"] else 0.0


@weave.op
def spl(output: dict) -> float:
    return float(output["spl"])


@weave.op
def collisions(output: dict) -> float:
    return float(output["collisions"])


@weave.op
def failures(output: dict) -> float:
    return float(len(output["failures"]))


def evaluate_map(belief: BeliefMap, world: TrueWorld, tasks: List[dict], label: str, story: str = "") -> dict:
    """Run a Weave Evaluation for this belief version; returns summary metrics + eval ref."""
    model = MapNavModel(map_name=belief.name, version=belief.version, belief_json=belief.to_json(), world_json=world.to_json())
    ev = weave.Evaluation(name=f"cogmap-{belief.name}", dataset=tasks, scorers=[success, spl, collisions, failures],
                          evaluation_name=label)
    summary = asyncio.run(ev.evaluate(model, __weave={"display_name": label}))
    out = {
        "label": label, "version": belief.version, "story": story,
        "success_rate": summary["success"]["mean"],
        "spl": summary["spl"]["mean"],
        "collisions": summary["collisions"]["mean"] * len(tasks),
        "failures": summary["failures"]["mean"] * len(tasks),
    }
    try:
        out["eval_ref"] = weave.publish(ev, name=f"eval-{label}").uri()
    except Exception:  # noqa: BLE001
        out["eval_ref"] = None
    return out


def weave_urls(project: str = "cogmap") -> dict:
    """Human-clickable Weave URLs for the README / dashboard."""
    try:
        client = weave.get_client()
        entity, proj = client.entity, client.project
    except Exception:  # noqa: BLE001
        entity, proj = "sissiwang-maglev", project
    base = f"https://wandb.ai/{entity}/{proj}/weave"
    return {"project": base, "evaluations": f"{base}/evaluations", "leaderboard": f"{base}/leaderboards/cogmap-map-versions",
            "traces": f"{base}/traces"}


def publish_leaderboard(eval_refs: List[str], name: str = "cogmap-map-versions") -> Optional[str]:
    try:
        from weave.flow import leaderboard
        cols = []
        for ref in eval_refs:
            cols.append(leaderboard.LeaderboardColumn(evaluation_object_ref=ref, scorer_name="success", summary_metric_path="mean"))
            cols.append(leaderboard.LeaderboardColumn(evaluation_object_ref=ref, scorer_name="spl", summary_metric_path="mean"))
        spec = leaderboard.Leaderboard(name=name, description="Navigation success per CogMap map version (higher is better).", columns=cols)
        return weave.publish(spec).uri()
    except Exception as e:  # noqa: BLE001
        print("leaderboard publish failed:", e)
        return None
