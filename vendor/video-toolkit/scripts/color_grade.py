#!/usr/bin/env python3
"""Colour grading: generate LUTs, apply .cube LUTs, match colour to a reference, finishing.

  color_grade.py gen-luts                       # (re)build luts/*.cube (teal_orange, cinematic, warm, bw, moody, vibrant)
  color_grade.py apply in.mp4 -o out.mp4 --lut teal_orange [--intensity 0.8]
  color_grade.py match in.mp4 -o out.mp4 --ref reference.mp4 [--strength 0.8] [--save-lut matched.cube]
  color_grade.py finish in.mp4 -o out.mp4 [--contrast 1.05 --saturation 1.1 --vignette --sharpen --grain 6]
--lut accepts a name from luts/ or any path to a .cube file.
Matching = Reinhard Lab mean/std transfer baked into a 33^3 LUT, so it is fast and reusable.
"""
import argparse, sys, tempfile
from pathlib import Path
import numpy as np, cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import ffmpeg, media_info, vcodec, LUTS_DIR, ass_escape_path

N = 33


def grid(n=N):
    r = np.linspace(0, 1, n)
    B, G, R = np.meshgrid(r, r, r, indexing="ij")  # R varies fastest in .cube order
    return np.stack([R, G, B], -1).reshape(-1, 3)


def write_cube(path, rgb, title, n=N):
    rgb = np.clip(rgb, 0, 1)
    with open(path, "w") as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        f.writelines(f"{r:.6f} {g:.6f} {b:.6f}\n" for r, g, b in rgb)


def luma(x): return x @ np.array([0.2126, 0.7152, 0.0722])


def contrast_s(x, amt=0.3):
    # smooth S-curve via logistic blend
    s = 1 / (1 + np.exp(-(x - 0.5) * 8))
    s = (s - s.min()) / (s.max() - s.min()) if np.ndim(s) and s.size > 1 else s
    return (1 - amt) * x + amt * s


def sat(x, s):
    y = luma(x)[:, None]
    return y + (x - y) * s


def gen_luts():
    LUTS_DIR.mkdir(exist_ok=True)
    g = grid()
    y = luma(g)[:, None]
    looks = {}
    # teal & orange: shadows -> teal, highlights/skin -> orange, mild S-curve
    t = contrast_s(g, 0.35)
    sh = np.clip(1 - y * 2, 0, 1); hi = np.clip(y * 2 - 1, 0, 1)
    t = t + sh * np.array([-0.06, 0.02, 0.06]) + hi * np.array([0.06, 0.015, -0.06])
    # push skin hues (r>g>b) further orange, blues to teal
    warmmask = np.clip((g[:, 0] - g[:, 2]) * 2, 0, 1)[:, None]
    t = t + warmmask * np.array([0.03, 0.0, -0.03]) + (1 - warmmask) * np.array([-0.02, 0.01, 0.02]) * (1 - y)
    looks["teal_orange"] = sat(t, 1.15)
    # cinematic: lifted blacks, rolled highlights, slight desat, cool shadows
    c = contrast_s(g, 0.45)
    c = 0.04 + c * 0.92
    c = c + sh * np.array([-0.015, 0.0, 0.025])
    looks["cinematic"] = sat(c, 0.85)
    # warm: golden hour
    w = g * np.array([1.06, 1.0, 0.88]) + 0.02 * np.array([1, 0.6, 0])
    looks["warm"] = sat(contrast_s(w, 0.2), 1.1)
    # bw: contrasty monochrome with red-filter weighting
    bw = contrast_s((g @ np.array([0.40, 0.45, 0.15]))[:, None].repeat(3, 1), 0.5)
    looks["bw"] = bw
    # moody: dark, desaturated, green-teal
    m = contrast_s(g, 0.3) * 0.9 + np.array([-0.01, 0.01, 0.015])
    looks["moody"] = sat(m, 0.7)
    # vibrant: social pop
    looks["vibrant"] = sat(contrast_s(g, 0.3), 1.35)
    for k, v in looks.items():
        write_cube(LUTS_DIR / f"{k}.cube", v, k)
    write_cube(LUTS_DIR / "identity.cube", g, "identity")
    print("LUTs:", ", ".join(sorted(p.stem for p in LUTS_DIR.glob("*.cube"))))


def resolve_lut(name):
    p = Path(name)
    if p.exists(): return p
    p = LUTS_DIR / f"{name}.cube"
    if p.exists(): return p
    sys.exit(f"LUT not found: {name} (available: {[x.stem for x in LUTS_DIR.glob('*.cube')]})")


def lut_filter(lut, intensity=1.0):
    f = f"lut3d=file='{ass_escape_path(lut)}':interp=tetrahedral"
    if intensity >= 0.999:
        return f"[0:v]{f},format=yuv420p[v]"
    return (f"[0:v]format=gbrp,split[o][g];[g]{f}[gg];[o][gg]blend=all_expr='A*(1-{intensity})+B*{intensity}',format=yuv420p[v]")


def render(inp, out, fc, fast=False):
    amap = ["-map", "0:a?", "-c:a", "copy"]
    ffmpeg(["-i", inp, "-filter_complex", fc, "-map", "[v]", *amap, *vcodec(fast), out])


def lab_stats(path, samples=60):
    """Float Lab mean/std over sampled frames (video) or one image."""
    imgs = []
    if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        imgs = [cv2.imread(str(path))]
    else:
        cap = cv2.VideoCapture(str(path)); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for i in np.linspace(0, max(n - 2, 0), min(samples, max(n, 1))).astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, f = cap.read()
            if ok: imgs.append(f)
        cap.release()
    px = []
    for f in imgs:
        f = cv2.resize(f, (256, int(256 * f.shape[0] / f.shape[1])))
        lab = cv2.cvtColor(f.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
        px.append(lab.reshape(-1, 3))
    px = np.concatenate(px)
    return px.mean(0), px.std(0)


def match_lut(src, ref, strength, out_cube):
    ms, ss = lab_stats(src); mr, sr = lab_stats(ref)
    ratio = np.clip(sr / np.maximum(ss, 1e-3), 0.5, 2.0)
    g = grid().astype(np.float32)
    bgr = g[:, ::-1].reshape(-1, 1, 3)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).reshape(-1, 3)
    t = (lab - ms) * ratio + mr
    lab2 = lab + strength * (t - lab)
    lab2[:, 0] = np.clip(lab2[:, 0], 0, 100)
    rgb = cv2.cvtColor(lab2.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_LAB2BGR).reshape(-1, 3)[:, ::-1]
    write_cube(out_cube, rgb, f"match_{Path(ref).stem}")
    return {"src_mean": ms.round(2).tolist(), "ref_mean": mr.round(2).tolist(), "src_std": ss.round(2).tolist(), "ref_std": sr.round(2).tolist()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("gen-luts")
    p = sp.add_parser("apply"); p.add_argument("input"); p.add_argument("-o", "--out", required=True)
    p.add_argument("--lut", required=True); p.add_argument("--intensity", type=float, default=1.0); p.add_argument("--fast", action="store_true")
    m = sp.add_parser("match"); m.add_argument("input"); m.add_argument("-o", "--out", required=True)
    m.add_argument("--ref", required=True); m.add_argument("--strength", type=float, default=0.8)
    m.add_argument("--save-lut"); m.add_argument("--then-lut", help="optional creative LUT after matching"); m.add_argument("--fast", action="store_true")
    f = sp.add_parser("finish"); f.add_argument("input"); f.add_argument("-o", "--out", required=True)
    f.add_argument("--contrast", type=float, default=1.0); f.add_argument("--saturation", type=float, default=1.0)
    f.add_argument("--brightness", type=float, default=0.0); f.add_argument("--gamma", type=float, default=1.0)
    f.add_argument("--vignette", action="store_true"); f.add_argument("--sharpen", action="store_true")
    f.add_argument("--grain", type=int, default=0); f.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    if a.cmd == "gen-luts":
        gen_luts()
    elif a.cmd == "apply":
        render(a.input, a.out, lut_filter(resolve_lut(a.lut), a.intensity), a.fast); print(f"wrote {a.out}")
    elif a.cmd == "match":
        cube = Path(a.save_lut) if a.save_lut else Path(tempfile.mkdtemp()) / "match.cube"
        st = match_lut(a.input, a.ref, a.strength, cube)
        fc = f"[0:v]lut3d=file='{ass_escape_path(cube)}':interp=tetrahedral"
        if a.then_lut:
            fc += f",lut3d=file='{ass_escape_path(resolve_lut(a.then_lut))}'"
        render(a.input, a.out, fc + ",format=yuv420p[v]", a.fast)
        print(f"wrote {a.out}  (Lab stats {st})" + (f", LUT saved {cube}" if a.save_lut else ""))
    else:
        ch = [f"eq=contrast={a.contrast}:saturation={a.saturation}:brightness={a.brightness}:gamma={a.gamma}"]
        if a.sharpen: ch.append("unsharp=5:5:0.6:5:5:0.0")
        if a.vignette: ch.append("vignette=angle=PI/5")
        if a.grain: ch.append(f"noise=c0s={a.grain}:c0f=t+u")
        render(a.input, a.out, f"[0:v]{','.join(ch)},format=yuv420p[v]", a.fast); print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
