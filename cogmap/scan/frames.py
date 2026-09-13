"""Keyframe extraction from a phone walkthrough video."""
from __future__ import annotations

import glob
import os
import subprocess
from typing import List


def video_duration(video: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def extract_frames(video: str, out_dir: str, n: int = 40, width: int = 1024) -> List[str]:
    """Evenly spaced JPEG frames (VGGT resizes to a 518 px long edge itself)."""
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, "frame_*.jpg")):
        os.remove(f)
    dur = max(video_duration(video), 0.1)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video,
                    "-vf", f"fps={n}/{dur},scale={width}:-2", "-q:v", "2", os.path.join(out_dir, "frame_%03d.jpg")],
                   check=True)
    frames = sorted(glob.glob(os.path.join(out_dir, "frame_*.jpg")))[:n]
    return frames


def contact_sheet(frames: List[str], out_path: str, cols: int = 6, width: int = 320) -> str:
    from PIL import Image
    imgs = [Image.open(f) for f in frames]
    if not imgs:
        return out_path
    w = width; h = int(imgs[0].height * w / imgs[0].width)
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "black")
    for i, im in enumerate(imgs):
        sheet.paste(im.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    sheet.save(out_path)
    return out_path
