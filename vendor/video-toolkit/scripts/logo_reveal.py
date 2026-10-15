"""Logo reveal (2-4s): styles 'pop' (scale back-out + glow + shine sweep), 'blur' (focus pull), 'wipe' (mask wipe). Adds whoosh+hit SFX.
vtk logo logo.png -o out.mp4 [--bg #0E0E10 | --bg-video bg.mp4] [--style pop --dur 3 --tagline "MELIA HOUSE"]"""
import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from vtk_common import vcodec, ACODEC, FONTS_DIR, TOOLKIT
a = argparse.ArgumentParser(); a.add_argument("logo"); a.add_argument("-o", required=True); a.add_argument("--bg", default="#0E0E10")
a.add_argument("--style", default="pop"); a.add_argument("--dur", type=float, default=3.0); a.add_argument("--tagline", default="")
a.add_argument("--W", type=int, default=1080); a.add_argument("--H", type=int, default=1920)
o = a.parse_args(); W, H, fps = o.W, o.H, 30
logo = Image.open(o.logo).convert("RGBA"); s = min(W * 0.6 / logo.width, H * 0.3 / logo.height); logo = logo.resize((int(logo.width * s), int(logo.height * s)), Image.LANCZOS)
bg = tuple(int(o.bg.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)); f = ImageFont.truetype(str(FONTS_DIR / "Montserrat-SemiBold.ttf"), 54)
def bo(x, k=1.9): x = min(max(x, 0), 1); x -= 1; return x * x * ((k + 1) * x + k) + 1
def eo(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def frame(t):
    im = Image.new("RGBA", (W, H), bg + (255,)); g = Image.new("RGBA", (W, H)); cx, cy = W // 2, int(H * 0.45)
    if o.style == "pop":
        sc = max(bo(t / 0.6), 0.01); L = logo.resize((max(1, int(logo.width * sc)), max(1, int(logo.height * sc))))
    else: L = logo.copy()
    if o.style == "blur": L = L.filter(ImageFilter.GaussianBlur(max(0, 30 * (1 - eo(t / 0.9))))); L.putalpha(L.split()[3].point(lambda v: int(v * eo(t / 0.5))))
    if o.style == "wipe":
        m = Image.new("L", L.size, 0); ImageDraw.Draw(m).rectangle([0, 0, int(L.width * eo(t / 0.8)), L.height], fill=255)
        L.putalpha(Image.composite(L.split()[3], m, m))
    pos = (cx - L.width // 2, cy - L.height // 2); g.alpha_composite(L, pos)
    glow = g.filter(ImageFilter.GaussianBlur(25)); im.alpha_composite(glow); im.alpha_composite(g)
    if 0.6 < t < 1.3:  # shine sweep
        sh = Image.new("L", (W, H), 0); x = int(-200 + (W + 400) * (t - 0.6) / 0.7)
        ImageDraw.Draw(sh).polygon([(x, 0), (x + 90, 0), (x - 210, H), (x - 300, H)], fill=150)
        sh = Image.composite(sh, Image.new("L", (W, H), 0), g.split()[3]); im.paste(Image.new("RGBA", (W, H), (255, 255, 255, 255)), (0, 0), sh)
    if o.tagline and t > 0.9:
        al = int(255 * eo((t - 0.9) / 0.5)); d = ImageDraw.Draw(im); d.text((cx, cy + logo.height // 2 + 80 + int(20 * (1 - al / 255))), o.tagline, font=f, fill=(255, 255, 255, al), anchor="mm")
    if t > o.dur - 0.4: im = Image.blend(im, Image.new("RGBA", (W, H), bg + (255,)), (t - o.dur + 0.4) / 0.4)
    return np.array(im.convert("RGB"))
sfx = TOOLKIT / "sfx"
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
       "-i", str(sfx / "whoosh.wav"), "-i", str(sfx / "hit.wav"), "-filter_complex",
       f"[1:a]volume=0.8[w];[2:a]adelay=450|450,volume=0.9[h];[w][h]amix=2:normalize=0,apad[a]", "-map", "0:v", "-map", "[a]", "-t", str(o.dur), *vcodec(), *ACODEC, o.o]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for i in range(int(o.dur * fps)): p.stdin.write(frame(i / fps).tobytes())
p.stdin.close(); assert p.wait() == 0; print(o.o)
