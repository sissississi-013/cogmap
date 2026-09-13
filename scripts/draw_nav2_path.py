"""Draw the Nav2 planner result on the exported map.  Usage: python scripts/draw_nav2_path.py out/<run>"""
import json, re, sys
from PIL import Image, ImageDraw

run = sys.argv[1].rstrip("/")
txt = open(f"{run}/nav2_proof/nav2_path.yaml").read()
res_txt = txt[txt.find("Result"):] if "Result" in txt else txt
pts = [(float(x), float(y)) for x, y in re.findall(r"position:\s*\n\s*x:\s*([-\d.e]+)\s*\n\s*y:\s*([-\d.e]+)", res_txt)]
im = Image.open(f"{run}/scan/nav2/map.pgm").convert("L"); W, H = im.size; up = 6
im = im.resize((W * up, H * up), Image.NEAREST).convert("RGB"); d = ImageDraw.Draw(im)
meta = json.load(open(f"{run}/scan/grid_meta.json")); res = meta["cell"]; lo = meta["origin_xy"]
wp = json.load(open(f"{run}/scan/nav2/waypoints.json"))["waypoints"]
def px(x, y): return (x - lo[0]) / res * up, (H - (y - lo[1]) / res) * up
for name, w in wp.items():
    x, y = px(w["x"], w["y"]); d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(180, 180, 180)); d.text((x + 6, y - 6), name, fill=(120, 120, 120))
if pts:
    poly = [px(x, y) for x, y in pts]
    d.line(poly, fill=(30, 120, 255), width=4)
    for p, col, lab in ((poly[0], (46, 204, 113), "start"), (poly[-1], (230, 57, 70), "goal")):
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=col); d.text((p[0] + 8, p[1] - 6), lab, fill=col)
status = "SUCCEEDED" if "SUCCEEDED" in txt else "FAILED"
d.text((8, 8), f"ROS 2 Nav2 (NavFn) on the CogMap map.pgm: /compute_path_to_pose -> {status}, {len(pts)} poses", fill=(30, 30, 30))
im.save(f"{run}/nav2_proof/nav2_path.png"); print(f"{run}/nav2_proof/nav2_path.png ({len(pts)} poses, {status})")
