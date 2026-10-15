"""Auto B-roll insertion over A-roll (keeps A-roll audio = L-cut style). Timing: explicit --at, or auto: every --every s
after the hook, avoiding first --hook s and last 2s, preferring sentence gaps from an SRT if given.
vtk broll aroll.mp4 -b clip1.mp4 clip2.mp4 ... -o out.mp4 [--at 3,8 --len 2.0 --every 5 --hook 3 --srt subs.srt --zoom 1.08]"""
import argparse, sys, os, re, json; sys.path.insert(0, os.path.dirname(__file__))
from vtk_common import ffmpeg, vcodec, ACODEC, media_info
a = argparse.ArgumentParser(); a.add_argument("aroll"); a.add_argument("-b", "--broll", nargs="+", required=True); a.add_argument("-o", required=True)
a.add_argument("--at"); a.add_argument("--len", type=float, default=2.0); a.add_argument("--every", type=float, default=5.0); a.add_argument("--hook", type=float, default=3.0)
a.add_argument("--srt"); a.add_argument("--zoom", type=float, default=1.08)
o = a.parse_args(); mi = media_info(o.aroll); D, W, H = mi["duration"], mi["width"], mi["height"]
if o.at: ts = [float(x) for x in o.at.split(",")]
else:
    cands = []
    if o.srt:  # caption starts = new sentences/ideas -> good cut points
        for m in re.finditer(r"(\d+):(\d+):(\d+),(\d+) -->", open(o.srt, encoding="utf-8").read()):
            h, mi_, s, ms = map(int, m.groups()); cands.append(h * 3600 + mi_ * 60 + s + ms / 1000)
    ts, t = [], o.hook
    while t < D - 2 - o.len:
        near = [c for c in cands if abs(c - t) < 1.5]; tt = min(near, key=lambda c: abs(c - t)) if near else t
        if not ts or tt - ts[-1] >= o.len + 1.0: ts.append(round(tt, 2))
        t += o.every
inputs, fc, prev = ["-i", o.aroll], [f"[0:v]fps=30,scale={W}:{H},setsar=1[v0]"], "v0"
for i, t in enumerate(ts):
    b = o.broll[i % len(o.broll)]; bd = media_info(b)["duration"]; L = min(o.len, bd)
    inputs += ["-i", b]; k = i + 1
    fc.append(f"[{k}:v]trim=0:{L},setpts=PTS-STARTPTS+{t}/TB,fps=30,scale={int(W*o.zoom)}:{int(H*o.zoom)}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H}:'(iw-{W})/2*(1+0.3*sin(t))':'(ih-{H})/2',setsar=1[b{k}]")
    fc.append(f"[{prev}][b{k}]overlay=enable='between(t,{t},{t+L})':eof_action=pass[v{k}]"); prev = f"v{k}"
ffmpeg([*inputs, "-filter_complex", ";".join(fc), "-map", f"[{prev}]", "-map", "0:a?", "-t", str(D), *vcodec(), *ACODEC, o.o])
print(json.dumps({"inserted_at": ts, "len": o.len}))
