#!/usr/bin/env python3
"""Transitions & impact effects.

1) JOIN clips with transitions (ffmpeg xfade + extra FX layered on the transition window):
   transitions.py join a.mp4 b.mp4 c.mp4 -t whip,flash -d 0.35 -o out.mp4 [--preset 1080p-9x16]
   Named transitions:
     crossfade  dissolve  dip (to black)  flash (white flash)  zoom (zoom-in morph)
     punch (fast cut + zoom punch)  whip / whip-right / whip-up (slide + directional motion blur)
     glitch (pixelize + RGB split + noise)  blur  wipe  circle  slide-up  smooth  squeeze
   Any raw xfade name (e.g. hlwind, radial, diagtl) also works. -t list cycles if shorter than cuts.

2) FX on a single clip at given times (seconds):
   transitions.py fx in.mp4 -o out.mp4 --punch 1.0,3.2 --flash 2.0 --glitch 4.1 --whip 5.0 --shake 6.0
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import ffmpeg, media_info, conform_filter, vcodec, ACODEC, PRESETS

XFADE = {"crossfade": "fade", "dissolve": "dissolve", "dip": "fadeblack", "flash": "fadewhite",
         "zoom": "zoomin", "punch": "fadefast", "whip": "slideleft", "whip-right": "slideright",
         "whip-up": "slideup", "glitch": "pixelize", "blur": "hblur", "wipe": "wipeleft",
         "circle": "circleopen", "slide-up": "slideup", "smooth": "smoothleft", "squeeze": "squeezeh"}


# ---------- time-windowed FX builders (return filter-chain fragments, ',' joined) ----------
def _win(times, d):
    return "+".join(f"between(t,{t:.3f},{t + d:.3f})" for t in times)


def fx_punch(times, W, H, amt=0.18, d=0.25):
    if not times: return []
    z = "+".join(f"{amt}*between(t,{t:.3f},{t + d:.3f})*(1-(t-{t:.3f})/{d})" for t in times)
    return [f"scale=w='trunc({W}*(1+{z})/2)*2':h='trunc({H}*(1+{z})/2)*2':eval=frame:flags=bicubic",
            f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2"]


def fx_flash(times, d=0.15, amt=0.7):
    if not times: return []
    b = "+".join(f"{amt}*between(t,{t:.3f},{t + d:.3f})*(1-(t-{t:.3f})/{d})" for t in times)
    return [f"eq=brightness='{b}':eval=frame"]


def fx_glitch(times, d=0.2):
    if not times: return []
    w1 = _win(times, d / 2); w2 = _win([t + d / 2 for t in times], d / 2)
    return [f"rgbashift=rh=-14:bh=14:rv=4:enable='{w1}'", f"rgbashift=rh=10:bh=-8:gv=-6:enable='{w2}'",
            f"noise=alls=35:allf=t:enable='{_win(times, d)}'"]


def fx_whip(times, d=0.25, angle=0):
    if not times: return []
    return [f"dblur=angle={angle}:radius=60:enable='{_win(times, d)}'"]


def fx_shake(times, W, H, d=0.4, amp=18):
    if not times: return []
    e = _win(times, d)
    return [f"scale={W + 4 * amp}:{H + 4 * amp}",
            f"crop={W}:{H}:x='{2 * amp}+({e})*{amp}*sin(t*73)':y='{2 * amp}+({e})*{amp}*cos(t*59)'"]


def build_post(kind_times, W, H, d):
    chain = []
    chain += fx_whip(kind_times.get("whip", []), d)
    chain += fx_whip(kind_times.get("whip-up", []), d, angle=90)
    chain += fx_glitch(kind_times.get("glitch", []), max(d, 0.2))
    chain += fx_punch(kind_times.get("punch", []), W, H)
    chain += fx_flash(kind_times.get("flash", []))
    chain += fx_shake(kind_times.get("shake", []), W, H)
    return chain


def cmd_join(a):
    W, H = PRESETS[a.preset] if a.preset else (None, None)
    infos = [media_info(c) for c in a.clips]
    if W is None:
        W, H = infos[0]["width"], infos[0]["height"]
    fps = a.fps
    names = a.transitions.split(",")
    n = len(a.clips)
    fc, durs = [], []
    for i, (c, inf) in enumerate(zip(a.clips, infos)):
        D = inf.get("vduration", inf["duration"])
        durs.append(D)
        fc.append(f"[{i}:v]{conform_filter(W, H, a.fit, fps)},trim=0:{D:.3f},setpts=PTS-STARTPTS,settb=AVTB,fps={fps}[v{i}]")
        if inf["has_audio"]:
            fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{D:.3f},apad=whole_dur={D:.3f},asetpts=PTS-STARTPTS[a{i}]")
        else:
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{D:.3f}[a{i}]")
    kind_times = {}
    vprev, aprev, length = "[v0]", "[a0]", durs[0]
    for k in range(1, n):
        name = names[(k - 1) % len(names)]
        d = 0.08 if name == "punch" else a.duration
        d = min(d, durs[k] / 2, length / 2)
        off = length - d
        xf = XFADE.get(name, name)
        fc.append(f"{vprev}[v{k}]xfade=transition={xf}:duration={d:.3f}:offset={off:.3f}[vx{k}]")
        fc.append(f"{aprev}[a{k}]acrossfade=d={d:.3f}:c1=tri:c2=tri[ax{k}]")
        vprev, aprev = f"[vx{k}]", f"[ax{k}]"
        if name in ("whip", "whip-right", "whip-up", "glitch"):
            kind_times.setdefault("whip-up" if name == "whip-up" else "glitch" if name == "glitch" else "whip", []).append(off)
        if name == "punch":
            kind_times.setdefault("punch", []).append(off + d)
        if name == "flash":
            kind_times.setdefault("flash", []).append(off + d / 2 - 0.05)
        length = length + durs[k] - d
    post = build_post(kind_times, W, H, a.duration)
    fc.append(f"{vprev}{','.join(post) if post else 'null'},format=yuv420p[vout]")
    args = []
    for c in a.clips:
        args += ["-i", c]
    ffmpeg([*args, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", aprev, *vcodec(a.fast), *ACODEC, a.out])
    print(f"wrote {a.out} ({length:.2f}s, {n} clips, transitions: {names})")


def cmd_fx(a):
    inf = media_info(a.input)
    W, H = inf["width"], inf["height"]
    parse = lambda s: [float(x) for x in s.split(",")] if s else []
    kt = {"punch": parse(a.punch), "flash": parse(a.flash), "glitch": parse(a.glitch),
          "whip": parse(a.whip), "shake": parse(a.shake)}
    post = build_post(kt, W, H, a.d)
    if not post:
        sys.exit("no effects requested")
    amap = ["-map", "0:a", "-c:a", "copy"] if inf["has_audio"] else []
    ffmpeg(["-i", a.input, "-filter_complex", f"[0:v]{','.join(post)},format=yuv420p[v]", "-map", "[v]", *amap,
            *vcodec(a.fast), a.out])
    print(f"wrote {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    j = sp.add_parser("join"); j.add_argument("clips", nargs="+"); j.add_argument("-o", "--out", required=True)
    j.add_argument("-t", "--transitions", default="crossfade"); j.add_argument("-d", "--duration", type=float, default=0.4)
    j.add_argument("--preset", default="1080p-9x16", choices=PRESETS.keys(), help="default 1080p-9x16 (vertical)"); j.add_argument("--fit", default="cover", choices=["cover", "fit", "blur"])
    j.add_argument("--fps", type=int, default=30); j.add_argument("--fast", action="store_true")
    f = sp.add_parser("fx"); f.add_argument("input"); f.add_argument("-o", "--out", required=True)
    for k in ("punch", "flash", "glitch", "whip", "shake"):
        f.add_argument(f"--{k}", help="comma-separated times (s)")
    f.add_argument("-d", type=float, default=0.25, help="effect window (s)"); f.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    (cmd_join if a.cmd == "join" else cmd_fx)(a)


if __name__ == "__main__":
    main()
