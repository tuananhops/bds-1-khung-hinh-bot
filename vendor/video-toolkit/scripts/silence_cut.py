"""Auto jump-cut: remove silences/dead air. vtk silencecut in.mp4 -o out.mp4 [--db -32 --min 0.35 --pad 0.08]"""
import argparse, sys, os, re, json; sys.path.insert(0, os.path.dirname(__file__))
from vtk_common import ffmpeg, run, vcodec, ACODEC, media_info
a = argparse.ArgumentParser(); a.add_argument("inp"); a.add_argument("-o", required=True)
a.add_argument("--db", type=float, default=-32); a.add_argument("--min", type=float, default=0.35); a.add_argument("--pad", type=float, default=0.08)
o = a.parse_args(); D = media_info(o.inp)["duration"]
err = run(["ffmpeg", "-hide_banner", "-i", o.inp, "-af", f"silencedetect=n={o.db}dB:d={o.min}", "-f", "null", "-"]).stderr
st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]; en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
if len(en) < len(st): en.append(D)
keep, cur = [], 0.0
for s, e in zip(st, en):
    if s + o.pad - cur > 0.05: keep.append((cur, s + o.pad))
    cur = max(cur, e - o.pad)
if D - cur > 0.05: keep.append((cur, D))
sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep)
ffmpeg(["-i", o.inp, "-vf", f"select='{sel}',setpts=N/FRAME_RATE/TB", "-af", f"aselect='{sel}',asetpts=N/SR/TB", *vcodec(), *ACODEC, o.o])
out = media_info(o.o)["duration"]; print(json.dumps({"segments": len(keep), "in": round(D, 2), "out": round(out, 2), "removed": round(D - out, 2)}))
