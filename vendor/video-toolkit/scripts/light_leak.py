"""Procedural light leaks / film burns / flash transitions, screen-blended. vtk leak in.mp4 -o out.mp4 [--at 2.0,5.5 --dur 0.8 --palette warm|cool|pink --strength 0.85]
Also: --flash for white flash at cut points; --grain adds film grain; --vignette."""
import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from fx_overlay import composite
from vtk_common import ffmpeg, vcodec, ACODEC
P = {"warm": [(255, 140, 40), (255, 60, 30), (255, 220, 120)], "cool": [(60, 140, 255), (160, 90, 255), (120, 255, 240)], "pink": [(255, 70, 170), (255, 150, 60), (200, 80, 255)]}
a = argparse.ArgumentParser(); a.add_argument("inp"); a.add_argument("-o", required=True); a.add_argument("--at", default="1.0")
a.add_argument("--dur", type=float, default=0.8); a.add_argument("--palette", default="warm"); a.add_argument("--strength", type=float, default=0.85)
a.add_argument("--grain", type=int, default=0); a.add_argument("--vignette", action="store_true")
o = a.parse_args(); ats = [float(x) for x in o.at.split(",")]; rng = np.random.default_rng(7); blobs = {}
def frame(t, W, H):
    img = np.zeros((H // 4, W // 4, 3), np.float32); h, w = img.shape[:2]
    for k, t0 in enumerate(ats):
        x = (t - t0) / o.dur
        if not -0.0 <= x <= 1: continue
        env = np.sin(np.pi * x) ** 1.5
        if k not in blobs: blobs[k] = [(rng.uniform(-.2, 1.2), rng.uniform(0, 1), rng.uniform(.25, .6), P[o.palette][j % 3]) for j in range(4)]
        for j, (bx, by, r, c) in enumerate(blobs[k]):
            cx = (bx + 0.5 * x * (1 if j % 2 else -1)) * w; cy = by * h
            yy, xx = np.mgrid[0:h, 0:w]; g = np.exp(-(((xx - cx) ** 2) / (2 * (r * w) ** 2) + ((yy - cy) ** 2) / (2 * (r * h * 0.7) ** 2)))
            img += g[..., None] * np.array(c, np.float32) * env * o.strength
    img = cv2.resize(np.clip(img, 0, 255), (W, H)); return np.dstack([img, np.full((H, W), 255, np.float32)]).astype(np.uint8)
tmp = o.o + ".tmp.mp4" if (o.grain or o.vignette) else o.o
composite(o.inp, tmp, frame, blend="screen")
if tmp != o.o:
    vf = ",".join(f for f in [f"noise=alls={o.grain}:allf=t" if o.grain else "", "vignette=PI/5" if o.vignette else ""] if f)
    ffmpeg(["-i", tmp, "-vf", vf, "-c:a", "copy", *vcodec(), o.o]); os.remove(tmp)
print(o.o)
