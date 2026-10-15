"""Scopes report: waveform + vectorscope + histogram sheet per sampled frame, plus exposure/saturation stats & warnings.
vtk scopes in.mp4 -o report_dir [--n 4]"""
import argparse, sys, os, re, json; sys.path.insert(0, os.path.dirname(__file__))
from vtk_common import ffmpeg, run, media_info
a = argparse.ArgumentParser(); a.add_argument("inp"); a.add_argument("-o", required=True); a.add_argument("--n", type=int, default=4)
o = a.parse_args(); os.makedirs(o.o, exist_ok=True); D = media_info(o.inp)["duration"]
for i in range(o.n):
    t = D * (i + 0.5) / o.n
    fc = ("[0:v]scale=540:-2,split=4[a][b][c][d];[b]waveform=mode=column:intensity=0.1:graticule=green:flags=numbers+dots:scale=ire,scale=540:400[w];"
          "[c]format=yuv444p,vectorscope=mode=color3:graticule=color:envelope=instant,scale=400:400[v];[d]histogram=display_mode=overlay,scale=540:400[h];"
          "[a]scale=540:-2[f];[f][w]vstack[l];[v][h]hstack,scale=540:-2[r];[l][r]vstack=inputs=2[out]")
    ffmpeg(["-ss", f"{t:.2f}", "-i", o.inp, "-frames:v", "1", "-filter_complex", fc, "-map", "[out]", f"{o.o}/scope_{i:02d}.png"])
err = run(["ffmpeg", "-hide_banner", "-i", o.inp, "-vf", "signalstats,metadata=print:file=-", "-an", "-f", "null", "-"]).stdout
def col(k): return [float(x) for x in re.findall(rf"lavfi.signalstats.{k}=([\d.]+)", err)]
Y, Ylo, Yhi, S = col("YAVG"), col("YLOW"), col("YHIGH"), col("SATAVG")
avg = lambda v: round(sum(v) / len(v), 1) if v else None
r = {"luma_avg_8bit": avg(Y), "luma_p10": avg(Ylo), "luma_p90": avg(Yhi), "sat_avg": avg(S), "warnings": []}
if r["luma_avg_8bit"] and r["luma_avg_8bit"] < 70: r["warnings"].append("underexposed: YAVG<70 (aim 90-130 for bright social)")
if r["luma_avg_8bit"] and r["luma_avg_8bit"] > 170: r["warnings"].append("overexposed: YAVG>170")
if r["luma_p90"] and r["luma_p90"] > 235: r["warnings"].append("highlights clipping (YHIGH>235)")
if r["luma_p10"] and r["luma_p10"] > 40: r["warnings"].append("lifted/washed blacks (YLOW>40) - add contrast")
if r["sat_avg"] and r["sat_avg"] < 20: r["warnings"].append("low saturation - flat/LOG? apply correction")
if r["sat_avg"] and r["sat_avg"] > 80: r["warnings"].append("oversaturated - check skin tones on vectorscope skin line")
json.dump(r, open(f"{o.o}/scopes.json", "w"), indent=2); print(json.dumps(r, ensure_ascii=False))
