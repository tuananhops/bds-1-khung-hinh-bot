"""Map extras missing from map_draw: (1) 3D extruded ground text lying on terrain (perspective quad), (2) red sweep/scan bar.
vtk mapfx base.mp4 -o out.mp4 --text "SÂN GOLF" --quad "300,1100,800,1100,900,1350,200,1350" [--t0 0.5 --color #FFFFFF --side #9AA3AD --depth 18]
                               --sweep [--sweep-color #FF2A2A --sweep-t0 0 --sweep-dur 1.2 --sweep-dir down]"""
import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fx_overlay import composite
from vtk_common import FONTS_DIR
def ease(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def extruded_text(text, font, face, side, depth):
    f = ImageFont.truetype(str(font), 200); l, t, r, b = f.getbbox(text)
    w, h = r - l + depth + 40, b - t + depth + 40; im = Image.new("RGBA", (w, h)); d = ImageDraw.Draw(im)
    for k in range(depth, 0, -1):  # extrusion layers, darker further back
        s = tuple(int(c * (0.6 + 0.4 * (1 - k / depth))) for c in side)
        d.text((20 - l + k * 0.6, 20 - t + k), text, font=f, fill=s + (255,))
    d.text((20 - l, 20 - t), text, font=f, fill=face + (255,), stroke_width=3, stroke_fill=(40, 40, 40, 255))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(im.split()[3].point(lambda v: v * 0.5)); sh = sh.filter(ImageFilter.GaussianBlur(8))
    out = Image.new("RGBA", im.size); out.alpha_composite(sh, (6, 10)); out.alpha_composite(im); return np.array(out)
a = argparse.ArgumentParser(); a.add_argument("base"); a.add_argument("-o", required=True)
a.add_argument("--text"); a.add_argument("--quad", help="TL,TR,BR,BL x,y pixels on output frame"); a.add_argument("--t0", type=float, default=0.3)
a.add_argument("--font", default="Montserrat-Black.ttf"); a.add_argument("--color", default="#FFFFFF"); a.add_argument("--side", default="#9AA3AD"); a.add_argument("--depth", type=int, default=18)
a.add_argument("--sweep", action="store_true"); a.add_argument("--sweep-color", default="#FF2A2A"); a.add_argument("--sweep-t0", type=float, default=0.0)
a.add_argument("--sweep-dur", type=float, default=1.2); a.add_argument("--sweep-dir", default="down")
o = a.parse_args()
tex = extruded_text(o.text, FONTS_DIR / o.font, hexrgb(o.color), hexrgb(o.side), o.depth) if o.text else None
cache = {}
def frame(t, W, H):
    canvas = np.zeros((H, W, 4), np.uint8)
    if tex is not None and t >= o.t0:
        p = ease((t - o.t0) / 0.6); q = np.array([float(v) for v in o.quad.split(",")]).reshape(4, 2)
        c = q.mean(0); q2 = c + (q - c) * (0.6 + 0.4 * p) - [0, 60 * (1 - p)]  # rise-in + grow
        h, w = tex.shape[:2]; M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), np.float32(q2))
        warped = cv2.warpPerspective(tex, M, (W, H), flags=cv2.INTER_LINEAR); warped[..., 3] = (warped[..., 3] * p).astype(np.uint8)
        canvas = warped
    if o.sweep and o.sweep_t0 <= t <= o.sweep_t0 + o.sweep_dur + 0.3:
        pr = ease((t - o.sweep_t0) / o.sweep_dur); rgb = hexrgb(o.sweep_color); L = H if o.sweep_dir in ("down", "up") else W
        pos = int(pr * L) if o.sweep_dir in ("down", "right") else int((1 - pr) * L)
        fade = 1 - max(0, (t - o.sweep_t0 - o.sweep_dur) / 0.3)
        bar = np.zeros((H, W, 4), np.float32); idx = np.arange(L, dtype=np.float32)
        trail = np.clip(1 - np.abs(idx - pos) / 14, 0, 1) + np.clip(1 - (pos - idx) / 260, 0, 1) * (idx < pos if o.sweep_dir in ("down", "right") else idx > pos) * 0.35
        trail = trail * fade
        if o.sweep_dir in ("down", "up"): al = np.repeat(trail[:, None], W, 1)
        else: al = np.repeat(trail[None, :], H, 0)
        bar[..., :3] = rgb; bar[..., 3] = al * 255
        core = (al > 0.9 * fade) if fade > 0 else al > 2
        bar[core, :3] = (255, 230, 230)
        ca = canvas.astype(np.float32); aa = bar[..., 3:4] / 255
        ca[..., :3] = bar[..., :3] * aa + ca[..., :3] * (1 - aa); ca[..., 3] = np.maximum(ca[..., 3], bar[..., 3]); canvas = ca.astype(np.uint8)
    return canvas
composite(o.base, o.o, frame); print(o.o)
