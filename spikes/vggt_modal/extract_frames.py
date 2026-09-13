"""Extract N evenly spaced frames from a video, resized to a max long edge (default 1024).
Uses OpenCV (ffmpeg on this machine is broken: missing libx265 dylib).
Usage: python3 extract_frames.py VIDEO OUT_DIR [N=40] [LONG_EDGE=1024]
"""
import sys, os, cv2, numpy as np

video, out = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
long_edge = int(sys.argv[4]) if len(sys.argv) > 4 else 1024
os.makedirs(out, exist_ok=True)
cap = cv2.VideoCapture(video)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
idxs = np.linspace(0, total - 1, n).astype(int)
saved = 0
for i, fi in enumerate(idxs):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
    ok, fr = cap.read()
    if not ok:
        print("failed to read frame", fi); continue
    h, w = fr.shape[:2]
    s = long_edge / max(h, w)
    if s < 1:
        fr = cv2.resize(fr, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out, f"frame_{i:03d}.jpg"), fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
    saved += 1
print(f"saved {saved} frames from {total} total to {out}; size {fr.shape[1]}x{fr.shape[0]}")
