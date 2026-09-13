"""Semantic objects: VLM labels + boxes per keyframe, anchored into grid cells via the VGGT point map."""
from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import numpy as np
import weave
from scipy import ndimage

from ..world import WorldObject, OCCUPIED, FREE
from .grid import world_to_cell

VOCAB = ["couch", "sofa", "armchair", "chair", "table", "coffee_table", "dining_table", "desk", "bed", "wardrobe", "cabinet",
         "bookshelf", "shelf", "tv", "tv_stand", "fridge", "kitchen_island", "counter", "oven", "plant", "lamp", "box",
         "door", "bathtub", "sink", "toilet", "washing_machine", "trash_can", "stool", "bench", "piano", "rug"]

DETECT_PROMPT = """You are labelling a frame from a phone walkthrough of a building for a robot's map.
List the distinct large physical objects a small ground robot must navigate around or could be sent to
(furniture, appliances, large plants, doors). Ignore walls, floor, ceiling, windows, small decor.
For each, give a snake_case name from this vocabulary when possible: %s
and a tight bounding box in normalized coordinates [x0,y0,x1,y1] with values 0-1000 (x right, y down).
Respond ONLY with JSON: {"objects":[{"name":"couch","box":[x0,y0,x1,y1]}, ...]}. Max 8 objects.""" % ", ".join(VOCAB)


def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


@weave.op
def detect_in_frame(frame_path: str, model: Optional[str] = None) -> dict:
    """VLM detection for one frame. Uses OpenAI (gpt-5) by default; Anthropic if COGMAP_LLM=anthropic."""
    provider = os.environ.get("COGMAP_LLM", "auto")
    if provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        m = model or os.environ.get("COGMAP_ANTHROPIC_MODEL", "claude-sonnet-5")
        msg = anthropic.Anthropic().messages.create(model=m, max_tokens=800, messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(frame_path)}},
            {"type": "text", "text": DETECT_PROMPT}]}])
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    else:
        from openai import OpenAI
        m = model or os.environ.get("COGMAP_OPENAI_VISION_MODEL", "gpt-5")
        r = OpenAI().chat.completions.create(model=m, response_format={"type": "json_object"}, max_completion_tokens=2500,
                                             reasoning_effort="low", messages=[{"role": "user", "content": [
                                                 {"type": "text", "text": DETECT_PROMPT},
                                                 {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(frame_path)}", "detail": "low"}}]}])
        raw = r.choices[0].message.content or ""
    try:
        start, end = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[start:end + 1])
        objs = [o for o in parsed.get("objects", []) if isinstance(o.get("box"), list) and len(o["box"]) == 4]
    except Exception:  # noqa: BLE001
        objs = []
    return {"frame": os.path.basename(frame_path), "objects": objs, "raw": raw[:2000]}


_OWL = {}


def _owlv2():
    """Lazy-load OWLv2 (open-vocabulary detector, CPU-friendly, no API key)."""
    if "model" not in _OWL:
        import torch
        from transformers import Owlv2Processor, Owlv2ForObjectDetection
        name = os.environ.get("COGMAP_OWLV2", "google/owlv2-base-patch16-ensemble")
        _OWL["proc"] = Owlv2Processor.from_pretrained(name)
        _OWL["model"] = Owlv2ForObjectDetection.from_pretrained(name).eval()
        _OWL["torch"] = torch
    return _OWL


OWL_QUERIES = ["a couch", "an armchair", "a chair", "a table", "a coffee table", "a dining table", "a desk", "a bed", "a wardrobe",
               "a cabinet", "a bookshelf", "a tv", "a fridge", "a kitchen island", "an oven", "a potted plant", "a box", "a sink",
               "a toilet", "a washing machine", "a trash can", "a stool", "a bench", "a piano", "a lamp"]
OWL_NAMES = ["couch", "armchair", "chair", "table", "coffee_table", "dining_table", "desk", "bed", "wardrobe", "cabinet", "bookshelf",
             "tv", "fridge", "kitchen_island", "oven", "plant", "box", "sink", "toilet", "washing_machine", "trash_can", "stool",
             "bench", "piano", "lamp"]


@weave.op
def detect_in_frame_owlv2(frame_path: str, threshold: float = 0.25, max_objects: int = 8) -> dict:
    """Local open-vocabulary detection (OWLv2). Same output format as detect_in_frame."""
    from PIL import Image
    o = _owlv2(); torch = o["torch"]
    im = Image.open(frame_path).convert("RGB")
    inputs = o["proc"](text=[OWL_QUERIES], images=im, return_tensors="pt")
    with torch.no_grad():
        out = o["model"](**inputs)
    # OWLv2 pads the image to a square; post-process wants the padded size
    side = max(im.size)
    pp = getattr(o["proc"], "post_process_grounded_object_detection", None) or o["proc"].post_process_object_detection
    try:
        res = pp(out, threshold=threshold, target_sizes=torch.tensor([[side, side]]), text_labels=[OWL_QUERIES])[0]
    except TypeError:
        res = pp(out, threshold=threshold, target_sizes=torch.tensor([[side, side]]))[0]
    objs = []
    labels = res["labels"].tolist() if hasattr(res["labels"], "tolist") else res["labels"]
    labels = [OWL_QUERIES.index(l) if isinstance(l, str) and l in OWL_QUERIES else l for l in labels]
    for score, label, box in sorted(zip(res["scores"].tolist(), labels, res["boxes"].tolist()), key=lambda t: -t[0]):
        x0, y0, x1, y1 = box
        if (x1 - x0) * (y1 - y0) > 0.6 * im.size[0] * im.size[1]:
            continue
        objs.append({"name": OWL_NAMES[label], "score": round(score, 3),
                     "box": [int(1000 * x0 / im.size[0]), int(1000 * y0 / im.size[1]), int(1000 * min(x1, im.size[0]) / im.size[0]), int(1000 * min(y1, im.size[1]) / im.size[1])]})
        if len(objs) >= max_objects:
            break
    return {"frame": os.path.basename(frame_path), "objects": objs, "raw": "owlv2"}


def detect_all(frames: List[str], every: int = 2, workers: int = 6) -> List[dict]:
    """API VLM first (fast, parallel); on API failure (no credits / bad key) fall back to local OWLv2 for all frames."""
    sel = frames[::every]
    mode = os.environ.get("COGMAP_DETECTOR", "auto")
    if mode != "owlv2":
        try:
            probe = detect_in_frame(sel[0])
            if probe["objects"] or "error" not in probe.get("raw", "").lower():
                with ThreadPoolExecutor(workers) as ex:
                    rest = list(ex.map(detect_in_frame, sel[1:]))
                return [probe] + rest
        except Exception as e:  # noqa: BLE001
            print(f"[scan] API detector unavailable ({str(e)[:80]}...) -> local OWLv2")
            if mode == "api":
                raise
    return [detect_in_frame_owlv2(f) for f in sel]


def _norm(name: str) -> str:
    n = name.lower().strip().replace(" ", "_")
    aliases = {"sofa": "couch", "settee": "couch", "shelf": "bookshelf", "television": "tv", "refrigerator": "fridge",
               "counter": "kitchen_island", "cupboard": "cabinet", "closet": "wardrobe"}
    return aliases.get(n, n)


NOT_NAV_GOALS = {"door", "rug", "lamp", "window", "wall", "floor", "ceiling", "mirror", "picture", "painting", "curtain"}


@weave.op
def anchor_objects(detections: List[dict], npz_path: str, frames: List[str], grid_info: dict, every: int = 2,
                   merge_dist_m: float = 1.5, min_cells: int = 1, max_objects: int = 12) -> dict:
    """Project each detection into the floor frame via the VGGT point map; merge across frames; build footprints."""
    d = np.load(npz_path)
    pts = d["world_points_from_depth"]           # (S,H,W,3)
    conf = d["depth_conf"].astype(np.float32)    # (S,H,W)
    S, H, W = conf.shape
    frame_index = {os.path.basename(f): i for i, f in enumerate(frames[:S])}
    Rw = np.array(grid_info["frame"]["R"]); ctr = np.array(grid_info["frame"]["ctr"]); s = grid_info["frame"]["scale"]
    lo = np.array(grid_info["origin_xy"]); cell = grid_info["cell"]
    grid = grid_info["grid"]
    cands: List[dict] = []
    for det in detections:
        i = frame_index.get(det["frame"])
        if i is None:
            continue
        for o in det["objects"]:
            if _norm(o["name"]) in NOT_NAV_GOALS:
                continue
            x0, y0, x1, y1 = [float(v) / 1000.0 for v in o["box"]]
            if (x1 - x0) * (y1 - y0) > 0.6:      # box covering most of the frame = wall/room, skip
                continue
            # inner 60% of the box, pixels in the VGGT image resolution
            cx0, cx1 = int((x0 + 0.2 * (x1 - x0)) * W), int((x1 - 0.2 * (x1 - x0)) * W)
            cy0, cy1 = int((y0 + 0.2 * (y1 - y0)) * H), int((y1 - 0.2 * (y1 - y0)) * H)
            cx0, cx1 = max(0, min(cx0, W - 1)), max(1, min(cx1, W))
            cy0, cy1 = max(0, min(cy0, H - 1)), max(1, min(cy1, H))
            if cx1 <= cx0 or cy1 <= cy0:
                continue
            P = pts[i, cy0:cy1, cx0:cx1].reshape(-1, 3).astype(np.float64)
            C = conf[i, cy0:cy1, cx0:cx1].reshape(-1)
            ok = np.isfinite(P).all(1) & (C >= np.percentile(C, 40))
            if ok.sum() < 20:
                continue
            Pl = (P[ok] - ctr) @ Rw.T * s        # floor frame, metres
            hz = Pl[:, 2]
            body = Pl[(hz > 0.05) & (hz < 2.0)]
            if len(body) < 10:
                body = Pl
            med = np.median(body, axis=0)
            cands.append({"name": _norm(o["name"]), "xy": med[:2].tolist(), "frame": det["frame"],
                          "body_xy": body[:, :2][np.random.default_rng(0).choice(len(body), min(len(body), 400), replace=False)].tolist()})
    # merge candidates of the same name within merge_dist
    clusters: List[dict] = []
    for c in sorted(cands, key=lambda c: c["name"]):
        hit = None
        for cl in clusters:
            if cl["name"] == c["name"] and np.hypot(cl["xy"][0] - c["xy"][0], cl["xy"][1] - c["xy"][1]) < merge_dist_m:
                hit = cl; break
        if hit is None:
            clusters.append({"name": c["name"], "xy": list(c["xy"]), "n": 1, "body_xy": list(c["body_xy"]), "frames": [c["frame"]]})
        else:
            k = hit["n"]
            hit["xy"] = [(hit["xy"][0] * k + c["xy"][0]) / (k + 1), (hit["xy"][1] * k + c["xy"][1]) / (k + 1)]
            hit["n"] += 1; hit["body_xy"] += c["body_xy"]; hit["frames"].append(c["frame"])
    # footprints: cells of body points (clipped to grid), at least the anchor cell; unique names
    objects: Dict[str, WorldObject] = {}
    counts: Dict[str, int] = {}
    free_adj = ndimage.binary_dilation(grid == FREE, iterations=2)
    for cl in sorted(clusters, key=lambda c: -c["n"]):
        if len(objects) >= max_objects:
            break
        xy = np.array(cl["body_xy"])
        cells_rc = ((xy - lo) / cell).astype(int)
        cells_rc = cells_rc[(cells_rc[:, 0] >= 0) & (cells_rc[:, 0] < grid.shape[1]) & (cells_rc[:, 1] >= 0) & (cells_rc[:, 1] < grid.shape[0])]
        if len(cells_rc) == 0:
            continue
        uniq, cnt = np.unique(cells_rc, axis=0, return_counts=True)
        keep = uniq[cnt >= max(2, int(np.percentile(cnt, 60)))]
        if len(keep) == 0:
            keep = uniq[np.argsort(-cnt)[:4]]
        keep = keep[:40]
        cells = [(int(r), int(c)) for c, r in keep]
        ar = int((cl["xy"][1] - lo[1]) / cell); ac = int((cl["xy"][0] - lo[0]) / cell)
        if 0 <= ar < grid.shape[0] and 0 <= ac < grid.shape[1] and (ar, ac) not in cells:
            cells.append((ar, ac))
        if len(cells) < min_cells or not any(free_adj[c] for c in cells):
            continue   # an object nobody can walk up to is useless as a navigation goal
        base = cl["name"]; counts[base] = counts.get(base, 0) + 1
        name = base if counts[base] == 1 else f"{base}_{counts[base]}"
        objects[name] = WorldObject(name, cells, kind="furniture", confidence=min(0.95, 0.5 + 0.1 * cl["n"]))
    return {"objects": {k: v.to_json() for k, v in objects.items()}, "n_candidates": len(cands), "n_clusters": len(clusters)}
