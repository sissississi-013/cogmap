"""Map repair: turn swarm failures + observations into a new belief version.

Two repair policies:
  * rule_repair  — deterministic, always runs (k-conflict cell flips, orphaned
                   objects, new obstacle blobs).
  * llm_repair   — Claude proposes scene-graph ops (relocate / add / remove) from
                   the failure log; every op is validated against the pooled
                   observations before it is applied.
Plus the outer loop pieces: volatility prior + patrol target selection.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import weave
from scipy import ndimage

from .agents import EpisodeResult, FailureEvent, pool_observations
from .world import BeliefMap, WorldObject, Cell, FREE, OCCUPIED, UNKNOWN

NEIGH4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _consensus(vals: List[int]) -> Tuple[int, float]:
    vals = [v for v in vals if v != UNKNOWN]
    if not vals:
        return UNKNOWN, 0.0
    occ = sum(v == OCCUPIED for v in vals)
    if occ * 2 >= len(vals):
        return OCCUPIED, occ / len(vals)
    return FREE, (len(vals) - occ) / len(vals)


@weave.op(name="cartographer_rule_repair")
def rule_repair(belief_json: dict, results_json: List[dict], observations: Dict[str, List[int]], k: int = 1) -> dict:
    """Deterministic repair. Returns {"belief": new_belief_json, "ops": [...], "changed": n}."""
    belief = BeliefMap.from_json(belief_json)
    ops: List[dict] = []
    changed: List[Cell] = []
    obs = {tuple(json.loads(kk)) if isinstance(kk, str) else tuple(kk): v for kk, v in observations.items()}

    # 1. cell-level consensus flips
    for cell, vals in obs.items():
        val, agreement = _consensus(vals)
        if val == UNKNOWN or len(vals) < k and belief.grid[cell] != UNKNOWN:
            continue
        if belief.grid[cell] != val:
            belief.set_cell(cell, val, min(0.99, 0.6 + 0.1 * len(vals)))
            changed.append(cell)
    if changed:
        ops.append({"op": "flip_cells", "n": len(changed)})

    # 2. orphaned objects: footprint observed free (ignoring cells shared with other objects), or agents that reached
    #    the goal cells and reported the object missing (goal_missing) at least twice
    missing_counts: Dict[str, int] = {}
    for r in results_json:
        for f in r.get("failures", []):
            if f.get("kind") == "goal_missing":
                missing_counts[f["goal"]] = missing_counts.get(f["goal"], 0) + 1
    shared = {}
    for name, o in belief.objects.items():
        for c in o.cells:
            shared.setdefault(c, set()).add(name)
    for name, o in list(belief.objects.items()):
        foot = [c for c in o.cells if belief.in_bounds(c) and shared.get(c, set()) == {name}]
        seen_free = sum(1 for c in foot if obs.get(c) and _consensus(obs[c])[0] == FREE)
        seen_occ = sum(1 for c in foot if obs.get(c) and _consensus(obs[c])[0] == OCCUPIED)
        by_obs = foot and ((seen_free >= 1 and seen_occ == 0) or seen_free >= max(1, len(foot) // 2))
        by_missing = missing_counts.get(name, 0) >= 2 and seen_occ <= len(foot) // 4
        if by_obs or by_missing:
            why = f"{seen_free}/{len(foot)} footprint cells observed free" if by_obs else f"reported missing by {missing_counts[name]} agents"
            ops.append({"op": "remove_object", "name": name, "reason": why})
            for c in o.cells:
                if belief.in_bounds(c) and belief.grid[c] == OCCUPIED and shared.get(c, set()) == {name} \
                        and not (obs.get(c) and _consensus(obs[c])[0] == OCCUPIED):
                    belief.set_cell(c, FREE, 0.7)
                    changed.append(c)
            del belief.objects[name]

    # 3. new obstacle blobs: occupied cells not explained by walls/objects -> unknown_obstacle_N
    explained = np.zeros(belief.shape, dtype=bool)
    for o in belief.objects.values():
        for c in o.cells:
            if belief.in_bounds(c):
                explained[c] = True
    newly_occ = np.zeros(belief.shape, dtype=bool)
    for cell in changed:
        if belief.grid[cell] == OCCUPIED and not explained[cell]:
            newly_occ[cell] = True
    labels, n = ndimage.label(newly_occ)
    for i in range(1, n + 1):
        cells = [tuple(int(x) for x in c) for c in np.argwhere(labels == i)]
        if len(cells) >= 2:
            name = f"unknown_obstacle_{belief.version + 1}_{i}"
            belief.objects[name] = WorldObject(name, cells, kind="obstacle", confidence=0.6)
            ops.append({"op": "add_object", "name": name, "n_cells": len(cells), "anchor": list(belief.objects[name].anchor)})

    # 4. re-identification: removed objects vs new unknown obstacles -> "the object moved here".
    #    Prefer objects the agents were actually looking for (goal_missing failures), then closest footprint size.
    missing_goals = [f["goal"] for r in results_json for f in r.get("failures", []) if f.get("kind") == "goal_missing"]
    removed = [o["name"] for o in ops if o["op"] == "remove_object"]
    removed_sizes = {n: len(belief_json["objects"][n]["cells"]) for n in removed}
    new_blobs = [o["name"] for o in ops if o["op"] == "add_object"]
    for nn in sorted(new_blobs, key=lambda n: -len(belief.objects[n].cells)):
        n_new = len(belief.objects[nn].cells)
        cands = [r for r in removed if n_new <= removed_sizes[r] * 2.0 and not r.startswith("unknown_obstacle")]
        if not cands:
            continue
        wanted = [r for r in cands if r in missing_goals]
        rn = wanted[0] if wanted else min(cands, key=lambda r: abs(removed_sizes[r] - n_new))
        removed.remove(rn)
        o = belief.objects.pop(nn)
        o.name, o.kind, o.confidence = rn, belief_json["objects"][rn].get("kind", "furniture"), 0.7
        belief.objects[rn] = o
        ops.append({"op": "rename", "name": nn, "new_name": rn,
                    "reason": f"{n_new}-cell blob matches removed {rn} ({removed_sizes[rn]} cells)" + (" [agents were searching for it]" if wanted else "")})

    belief.bump("rule_repair: " + "; ".join(o["op"] + ("(" + o.get("name", "") + ")" if "name" in o else "") for o in ops), changed)
    return {"belief": belief.to_json(), "ops": ops, "changed": len(changed)}


# ---------------------------------------------------------------------------
# LLM repair (Claude) over the scene graph
# ---------------------------------------------------------------------------

REPAIR_SYSTEM = """You are the map-repair agent for a fleet of navigation robots.
You receive the robots' current cognitive map (a scene graph of named objects with grid footprints),
a log of navigation failures (expected vs observed cell values, missing goals), and the pooled sensor
observations. Propose the SMALLEST set of scene-graph operations that explains the failures.
Operations (JSON list), each one of:
  {"op":"relocate","name":<existing object>,"to":[row,col], "why":...}   # object moved; footprint keeps its shape
  {"op":"remove","name":<existing object>, "why":...}                    # object gone
  {"op":"add","name":<new snake_case name>,"cells":[[r,c],...], "why":...} # new obstacle observed
  {"op":"rename","name":<existing>, "new_name":<better name>, "why":...}  # e.g. unknown_obstacle -> couch, if a removed object of the same size reappeared elsewhere
Rules: only use cells inside the grid; never mark a cell free that robots observed occupied; prefer
'rename' when a removed object's footprint size matches a new unknown obstacle (that's the object that moved).
IMPORTANT: a deterministic rule-repair pass has ALREADY been applied to the map you receive (its ops are listed under
rule_repair_applied). The failure log was recorded BEFORE that pass, so many failures are already explained. Do not undo
rule-repair ops (e.g. do not remove an object it just re-identified/renamed). Every op you propose is validated against
the robots' observations and rejected if unsupported, so propose only ops with evidence; an empty list is a fine answer.
Respond with JSON: {"ops":[...], "summary": "<one sentence for the human changelog>"}"""


def _chat_json(system: str, user: str, model: Optional[str] = None) -> Tuple[str, str]:
    """Call an LLM and return (raw_text, model_used). Tries Anthropic first, falls back to OpenAI."""
    errors = []
    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("COGMAP_LLM", "auto") in ("auto", "anthropic"):
        try:
            import anthropic
            m = model or os.environ.get("COGMAP_ANTHROPIC_MODEL", "claude-sonnet-5")
            msg = anthropic.Anthropic().messages.create(model=m, max_tokens=1500, system=system,
                                                        messages=[{"role": "user", "content": user}])
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text"), m
        except Exception as e:  # noqa: BLE001
            errors.append(f"anthropic: {e}")
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            m = os.environ.get("COGMAP_OPENAI_MODEL", "gpt-5")
            r = OpenAI().chat.completions.create(model=m, messages=[{"role": "system", "content": system},
                                                                    {"role": "user", "content": user}],
                                                 response_format={"type": "json_object"}, max_completion_tokens=4000,
                                                 reasoning_effort="low")
            return r.choices[0].message.content or "", m
        except Exception as e:  # noqa: BLE001
            errors.append(f"openai: {e}")
    raise RuntimeError("no LLM provider worked: " + " | ".join(errors))


@weave.op(name="reasoner_propose_ops")
def llm_propose_ops(belief_json: dict, failures: List[dict], removed: List[dict], added: List[dict],
                    model: Optional[str] = None, rule_ops: Optional[List[dict]] = None) -> dict:
    """Ask an LLM for scene-graph ops. Returns {"ops": [...], "summary": str, "raw": str, "model": str}."""
    objs = {k: {"anchor": v["anchor"], "n_cells": len(v["cells"]), "kind": v["kind"]} for k, v in belief_json["objects"].items()}
    H = len(belief_json["grid"]); W = len(belief_json["grid"][0])
    fail_summary: Dict[str, int] = {}
    for f in failures:
        key = f"{f['kind']}@{tuple(f['cell'])}" if f["kind"] != "goal_missing" else f"goal_missing:{f['goal']}"
        fail_summary[key] = fail_summary.get(key, 0) + 1
    user = json.dumps({
        "grid_shape": [H, W],
        "objects": objs,
        "failures_grouped": dict(sorted(fail_summary.items(), key=lambda kv: -kv[1])[:40]),
        "rule_repair_applied": {"removed_objects": removed, "added_unknown_obstacles": added,
                                "other_ops": [o for o in (rule_ops or []) if o["op"] not in ("remove_object", "add_object")]},
    }, indent=1)
    raw, used = _chat_json(REPAIR_SYSTEM, user, model)
    try:
        start, end = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[start:end + 1])
    except Exception:  # noqa: BLE001
        parsed = {"ops": [], "summary": "LLM output unparseable"}
    parsed["raw"] = raw
    parsed["model"] = used
    return parsed


@weave.op(name="verifier_apply_ops")
def validate_and_apply_ops(belief_json: dict, ops: List[dict], observations: Dict[str, List[int]]) -> dict:
    """Apply only ops consistent with observations. Returns {"belief":..., "applied":[...], "rejected":[...]}"""
    belief = BeliefMap.from_json(belief_json)
    obs = {tuple(json.loads(kk)) if isinstance(kk, str) else tuple(kk): v for kk, v in observations.items()}
    applied, rejected, changed = [], [], []

    def observed_free(c):
        return c in obs and _consensus(obs[c])[0] == FREE

    def observed_occ(c):
        return c in obs and _consensus(obs[c])[0] == OCCUPIED

    for op in ops:
        kind = op.get("op")
        try:
            if kind == "relocate":
                o = belief.objects[op["name"]]
                ar, ac = o.anchor
                tr, tc = int(op["to"][0]), int(op["to"][1])
                new_cells = [(r + tr - ar, c + tc - ac) for r, c in o.cells]
                if not all(belief.in_bounds(c) for c in new_cells):
                    raise ValueError("out of bounds")
                if any(observed_free(c) for c in new_cells):
                    raise ValueError("target footprint observed free")
                if not any(observed_occ(c) for c in new_cells):
                    raise ValueError("no observation supports an object at the target")
                if any(observed_occ(c) for c in o.cells) and not any(observed_free(c) for c in o.cells):
                    raise ValueError("object still observed at its current location")
                for c in o.cells:
                    if not observed_occ(c):
                        belief.set_cell(c, FREE, 0.7); changed.append(c)
                o.cells = new_cells
                belief.stamp_object(o, OCCUPIED, 0.75); changed += new_cells
            elif kind == "remove":
                o = belief.objects[op["name"]]
                if any(observed_occ(c) for c in o.cells):
                    raise ValueError("footprint still observed occupied")
                if not any(observed_free(c) for c in o.cells):
                    raise ValueError("no observation shows the object is gone")
                belief.objects.pop(op["name"])
                for c in o.cells:
                    if not observed_occ(c):
                        belief.set_cell(c, FREE, 0.7); changed.append(c)
            elif kind == "add":
                cells = [tuple(int(x) for x in c) for c in op["cells"]]
                if not all(belief.in_bounds(c) for c in cells) or any(observed_free(c) for c in cells):
                    raise ValueError("cells invalid or observed free")
                if not all(observed_occ(c) for c in cells):
                    raise ValueError("every added cell must have been observed occupied")
                belief.objects[op["name"]] = WorldObject(op["name"], cells, kind="obstacle", confidence=0.6)
                belief.stamp_object(belief.objects[op["name"]], OCCUPIED, 0.7); changed += cells
            elif kind == "rename":
                o = belief.objects.pop(op["name"])
                o.name = op["new_name"]; o.kind = "furniture"; o.confidence = 0.8
                belief.objects[o.name] = o
            else:
                raise ValueError(f"unknown op {kind}")
            applied.append(op)
        except Exception as e:  # noqa: BLE001
            rejected.append({**op, "reject_reason": str(e)})
    if applied:
        belief.bump("llm_repair: " + "; ".join(f"{o['op']}({o.get('name','')})" for o in applied), changed)
    return {"belief": belief.to_json(), "applied": applied, "rejected": rejected}


# ---------------------------------------------------------------------------
# Outer loop: volatility prior -> patrol targets
# ---------------------------------------------------------------------------

@weave.op(name="scout_pick_targets")
def patrol_targets(belief_json: dict, n: int = 6) -> List[List[int]]:
    """Cells the swarm should verify first: high volatility x low confidence, spread out."""
    b = BeliefMap.from_json(belief_json)
    score = b.volatility * (1.2 - b.confidence)
    score[b.grid == OCCUPIED] *= 0.5
    targets: List[List[int]] = []
    s = score.copy()
    for _ in range(n):
        idx = np.unravel_index(int(np.argmax(s)), s.shape)
        if s[idx] <= 1e-6:
            break
        targets.append([int(idx[0]), int(idx[1])])
        r, c = idx
        s[max(0, r - 3):r + 4, max(0, c - 3):c + 4] = 0  # spread targets out
    return targets


@weave.op(name="reflector_changelog")
def reflect(changelog: List[dict], round_stories: List[str], metrics: List[dict]) -> str:
    """Human-readable changelog (no LLM; deterministic so it always exists)."""
    lines = ["# CogMap changelog", ""]
    for m in metrics:
        lines.append(f"- **{m['label']}** (map v{m['version']}): success {m['success_rate']:.0%}, SPL {m['spl']:.2f}, collisions {m['collisions']}"
                     + (f" — {m['story']}" if m.get('story') else ""))
    lines.append("")
    lines.append("## Map versions")
    for e in changelog:
        lines.append(f"- v{e['version']}: {e['note']} ({e['n_changed']} cells changed)")
    return "\n".join(lines)


@weave.op(name="scout_search_sweep")
def search_targets(belief_json: dict, observed_cells: List[List[int]], stride: int = 5, n: int = 60) -> List[List[int]]:
    """Coverage sweep targets for finding a missing object: a lattice of free cells not observed this round,
    visited in nearest-neighbour order (a cheap TSP tour)."""
    b = BeliefMap.from_json(belief_json)
    seen = {tuple(c) for c in observed_cells}
    cand = []
    for r in range(2, b.shape[0] - 2, stride):
        for c in range(2, b.shape[1] - 2, stride):
            if b.grid[r, c] == FREE and (r, c) not in seen:
                cand.append((r, c))
    tour: List[List[int]] = []
    cur = cand[0] if cand else None
    while cand and len(tour) < n:
        nxt = min(cand, key=lambda t: abs(t[0] - cur[0]) + abs(t[1] - cur[1]))
        cand.remove(nxt)
        tour.append([nxt[0], nxt[1]])
        cur = nxt
    return tour


REFLECT_SYSTEM = """You are the Reflector for a fleet of navigation robots that maintain a shared cognitive map.
Given the per-round record (what changed in the world, how the swarm's success/collisions moved, how many repair passes,
how many rule ops and LLM ops were applied/rejected, and whether a patrol caught the change before tasks ran), write a
concise engineering post-mortem in Markdown: one short paragraph per round (what broke, what evidence the swarm collected,
what the repair did, what it cost) and a final paragraph 'What the swarm learned' about where the world is volatile and
what to patrol next. Be factual; do not invent numbers. Respond as JSON: {"markdown": "<the post-mortem in Markdown>"}"""


@weave.op(name="reflector_llm_postmortem")
def llm_reflect(rounds: List[dict], timeline: List[dict]) -> str:
    slim_tl = [{k: v for k, v in m.items() if k in ("label", "version", "success_rate", "spl", "collisions", "failures", "round", "phase")}
               for m in timeline]
    slim_r = [{k: v for k, v in r.items() if k != "perturbation"} for r in rounds]
    raw, used = _chat_json(REFLECT_SYSTEM, json.dumps({"rounds": slim_r, "timeline": slim_tl}, indent=1))
    # _chat_json asks OpenAI for a JSON object; accept either a {"markdown": ...} object or plain text
    try:
        start, end = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[start:end + 1])
        text = obj.get("markdown") or obj.get("text") or obj.get("postmortem") or "\n".join(str(v) for v in obj.values())
    except Exception:  # noqa: BLE001
        text = raw
    return f"## Reflector post-mortem ({used})\n\n" + text.strip()
