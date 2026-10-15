#!/usr/bin/env python3
"""Speed ramping (smooth, keyframed) with optional optical-flow slow motion.

  speed_ramp.py in.mp4 -o out.mp4 --keys "0:1,1.5:1,1.8:0.3,3:0.3,3.3:2.5,4.5:1"
  speed_ramp.py in.mp4 -o out.mp4 --hero 2.0            # fast-in -> slow-mo -> fast-out around t=2.0
  speed_ramp.py in.mp4 -o out.mp4 --constant 0.5 --interp mci   # plain 50% slow-mo with motion interpolation
Keys are SOURCE-time:speed pairs; speed is linearly interpolated between keys
(1=normal, 0.25=4x slow, 3=3x fast). --interp: none | blend | mci (optical flow, slow but smooth).
--audio keep (pitch-preserving atempo) | mute.
"""
import argparse, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import ffmpeg, media_info, vcodec, ACODEC


def atempo_chain(s):
    parts = []
    while s < 0.5:
        parts.append("atempo=0.5"); s /= 0.5
    while s > 2.0:
        parts.append("atempo=2.0"); s /= 2.0
    parts.append(f"atempo={s:.5f}")
    return ",".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--keys"); g.add_argument("--hero", type=float); g.add_argument("--constant", type=float)
    ap.add_argument("--step", type=float, default=0.1, help="source seconds per piece for smooth ramps")
    ap.add_argument("--interp", default="blend", choices=["none", "blend", "mci"])
    ap.add_argument("--audio", default="keep", choices=["keep", "mute"])
    ap.add_argument("--fps", type=int, default=None); ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    inf = media_info(a.input); D = inf.get("vduration", inf["duration"]); fps = a.fps or round(inf["fps"])
    if a.constant:
        keys = [(0, a.constant), (D, a.constant)]
    elif a.hero is not None:
        T = a.hero
        keys = [(0, 1), (max(0, T - 0.6), 1), (max(0, T - 0.25), 2.0), (T, 0.3), (T + 0.9, 0.3), (T + 1.2, 2.0), (T + 1.6, 1), (D, 1)]
    else:
        keys = [tuple(map(float, k.split(":"))) for k in a.keys.split(",")]
    keys = sorted(keys); kt = [k[0] for k in keys]; ks = [k[1] for k in keys]
    edges = list(np.arange(0, D, a.step)) + [D]
    if a.constant:
        edges = [0, D]
    pieces = [(s, e, float(np.interp((s + e) / 2, kt, ks))) for s, e in zip(edges, edges[1:]) if e - s > 1e-3]
    # merge neighbours with equal speed
    merged = []
    for p in pieces:
        if merged and abs(merged[-1][2] - p[2]) < 1e-3:
            merged[-1] = (merged[-1][0], p[1], p[2])
        else:
            merged.append(p)
    n = len(merged); keep_a = inf["has_audio"] and a.audio == "keep"
    fc = [f"[0:v]split={n}" + "".join(f"[vs{i}]" for i in range(n))] if n > 1 else ["[0:v]null[vs0]"]
    if keep_a:
        fc.append(f"[0:a]asplit={n}" + "".join(f"[as{i}]" for i in range(n)) if n > 1 else "[0:a]anull[as0]")
    for i, (s, e, sp) in enumerate(merged):
        fc.append(f"[vs{i}]trim={s:.4f}:{e:.4f},setpts=(PTS-STARTPTS)/{sp:.5f}[v{i}]")
        if keep_a:
            fc.append(f"[as{i}]atrim={s:.4f}:{e:.4f},asetpts=PTS-STARTPTS,{atempo_chain(sp)}[a{i}]")
    ins = "".join(f"[v{i}]" + (f"[a{i}]" if keep_a else "") for i in range(n))
    fc.append(f"{ins}concat=n={n}:v=1:a={1 if keep_a else 0}[vc]" + ("[ac]" if keep_a else ""))
    post = {"none": f"fps={fps}", "blend": f"framerate=fps={fps}:interp_start=0:interp_end=255:scene=100",
            "mci": f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"}[a.interp]
    fc.append(f"[vc]{post},format=yuv420p[vout]")
    amap = ["-map", "[ac]", *ACODEC] if keep_a else []
    ffmpeg(["-i", a.input, "-filter_complex", ";".join(fc), "-map", "[vout]", *amap, *vcodec(a.fast), a.out])
    outd = sum((e - s) / sp for s, e, sp in merged)
    print(f"wrote {a.out}: {len(merged)} pieces, {D:.2f}s -> {outd:.2f}s")


if __name__ == "__main__":
    main()
