"""Auto QC before export. vtk qc final.mp4 [--srt subs.srt|--ass subs.ass] [--platform tiktok|reels|shorts|all] [--lufs -14] [--json report.json]
Checks: container/codec/res/fps/bitrate, duration, integrated loudness & true peak, black frames, frozen frames, long silences,
first-frame black (bad hook), safe-zone intrusion (edge/text density in UI zones), caption timing/CPS/line length/overlap."""
import argparse, sys, os, re, json; sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from vtk_common import run, probe, media_info
SZ = {"tiktok": (240, 660, 120, 120, (840, 300)), "reels": (269, 672, 65, 65, None), "shorts": (288, 672, 48, 192, None), "all": (288, 672, 120, 192, (840, 300))}
a = argparse.ArgumentParser(); a.add_argument("inp"); a.add_argument("--srt"); a.add_argument("--ass"); a.add_argument("--platform", default="all")
a.add_argument("--lufs", type=float, default=-14); a.add_argument("--json")
o = a.parse_args(); R = {"file": o.inp, "fail": [], "warn": [], "pass": []}
F, Wn, P = R["fail"].append, R["warn"].append, R["pass"].append
d = probe(o.inp); v = next(s for s in d["streams"] if s["codec_type"] == "video"); au = [s for s in d["streams"] if s["codec_type"] == "audio"]
mi = media_info(o.inp); D = mi["duration"]; br = int(d["format"].get("bit_rate", 0)) / 1e6
(P if (v["width"], v["height"]) == (1080, 1920) else F)(f"resolution {v['width']}x{v['height']} (target 1080x1920)")
(P if v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p" else Wn)(f"codec {v['codec_name']} {v.get('pix_fmt')} (target h264 yuv420p)")
(P if 23 <= mi["fps"] <= 60.1 else F)(f"fps {mi['fps']:.2f}")
(P if 8 <= br <= 30 else Wn)(f"bitrate {br:.1f} Mbps (target 10-20)")
(P if 7 <= D <= 180 else Wn)(f"duration {D:.1f}s (sweet spot 15-60s; Shorts max 180s)")
if not au: F("no audio track")
else:
    (P if au[0]["codec_name"] == "aac" and au[0].get("sample_rate") == "48000" else Wn)(f"audio {au[0]['codec_name']} {au[0].get('sample_rate')}Hz")
    e = run(["ffmpeg", "-hide_banner", "-i", o.inp, "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    R["loudness"] = {"I": I, "TP": TP}
    (P if abs(I - o.lufs) <= 1.5 else F)(f"integrated loudness {I} LUFS (target {o.lufs}±1.5)")
    (P if TP <= -1.0 else F)(f"true peak {TP} dBTP (max -1.0)")
    s = run(["ffmpeg", "-hide_banner", "-i", o.inp, "-af", "silencedetect=n=-45dB:d=1.2", "-f", "null", "-"]).stderr
    sil = re.findall(r"silence_start: ([\d.]+)", s); (Wn if sil else P)(f"silences >1.2s at {sil[:6]}" if sil else "no dead-air >1.2s")
e = run(["ffmpeg", "-hide_banner", "-i", o.inp, "-vf", "blackdetect=d=0.1:pix_th=0.10,freezedetect=n=0.003:d=1.5", "-an", "-f", "null", "-"]).stderr
bl = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", e); fr = re.findall(r"freeze_start: ([\d.]+)", e)
for b0, b1 in bl: (F if float(b0) < 0.1 else Wn)(f"black frames {b0}-{b1}s" + (" (video opens on black = weak hook)" if float(b0) < 0.1 else ""))
if not bl: P("no black frames")
(Wn if fr else P)(f"frozen frames at {fr[:5]}" if fr else "no frozen frames")
# safe zone: compare text-like edge density in UI zones vs centre, on sampled frames
top, bot, l, r, rail = SZ[o.platform]; cap = cv2.VideoCapture(o.inp); hits = []
for t in np.linspace(0.5, max(D - 0.5, 0.6), 12):
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr_ = cap.read()
    if not ok: continue
    g = cv2.cvtColor(cv2.resize(fr_, (1080, 1920)), cv2.COLOR_BGR2GRAY); _, th = cv2.threshold(g, 235, 255, cv2.THRESH_BINARY)
    edges = cv2.Canny(g, 200, 400) & cv2.dilate(th, None)  # bright high-contrast strokes ~ white text/logos
    zones = {"top": edges[:top], "bottom": edges[1920 - bot:], "right_rail": edges[rail[0]:, 1080 - rail[1]:] if rail else edges[:, 1080 - r:]}
    for k, z in zones.items():
        if z.mean() > 0.5: hits.append(f"{k}@{t:.1f}s")
(Wn if hits else P)(f"possible text/logo inside UI zones: {hits[:8]}" if hits else f"safe zone ({o.platform}) clear")
cf = o.srt or o.ass
if cf:
    txt = open(cf, encoding="utf-8").read(); cues = []
    if o.srt:
        for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)\s*\n(.+?)(?:\n\n|\Z)", txt, re.S):
            g_ = list(map(int, m.groups()[:8])); cues.append((g_[0]*3600+g_[1]*60+g_[2]+g_[3]/1000, g_[4]*3600+g_[5]*60+g_[6]+g_[7]/1000, m.group(9).strip()))
    else:
        for m in re.finditer(r"Dialogue:[^,]*,(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),(?:[^,]*,){5}(.*)", txt):
            g_ = m.groups(); cues.append((int(g_[0])*3600+int(g_[1])*60+float(g_[2]), int(g_[3])*3600+int(g_[4])*60+float(g_[5]), re.sub(r"\{.*?\}", "", g_[6]).replace("\\N", "\n")))
    bad = []
    for i, (s0, s1, tx) in enumerate(cues):
        dur = s1 - s0; ch = len(tx.replace("\n", "")); lines = tx.split("\n")
        if dur < 0.3: bad.append(f"#{i+1} too short {dur:.2f}s")
        if ch / max(dur, 0.01) > 20: bad.append(f"#{i+1} {ch/dur:.0f} chars/s (>20)")
        if max(len(x) for x in lines) > 32 or len(lines) > 2: bad.append(f"#{i+1} line too long/too many lines")
        if i and s0 < cues[i-1][1] - 0.01: bad.append(f"#{i+1} overlaps previous")
        if s1 > D + 0.1: bad.append(f"#{i+1} past video end")
    cov = sum(c[1] - c[0] for c in cues) / D if D else 0
    (Wn if bad else P)(f"captions issues: {bad[:10]}" if bad else f"{len(cues)} captions OK")
    (P if cov > 0.5 else Wn)(f"caption coverage {cov:.0%}")
else: Wn("no caption file given - remember ~80% watch muted")
R["verdict"] = "FAIL" if R["fail"] else ("PASS with warnings" if R["warn"] else "PASS")
print(json.dumps(R, ensure_ascii=False, indent=1))
if o.json: json.dump(R, open(o.json, "w"), ensure_ascii=False, indent=1)
sys.exit(1 if R["fail"] else 0)
