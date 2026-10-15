#!/usr/bin/env python3
"""Audio finishing: loudness normalisation, music ducking under voice, mixing, SFX.

  audio.py loudnorm in.mp4 -o out.mp4 [--lufs -14 --tp -1]          # 2-pass EBU R128 (video stream copied)
  audio.py measure in.mp4                                            # print LUFS / true peak / LRA
  audio.py mix in.mp4 --music song.mp3 -o out.mp4 [--music-db -8 --duck --music-start 12 --fade 1.5]
        (voice = the video's own audio; with --duck the music is side-chain compressed under speech)
  audio.py sfx in.mp4 -o out.mp4 --at 1.0:whoosh,2.5:hit,4:riser [--sfx-db -6]
  audio.py gen-sfx                                                   # synthesize sfx/{whoosh,hit,riser,glitch,pop}.wav
  audio.py denoise in.mp4 -o out.mp4                                 # light speech clean-up (afftdn + highpass)
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import ffmpeg, media_info, ACODEC, TOOLKIT

SFX_DIR = TOOLKIT / "sfx"


def measure(path, extra_af=None):
    af = (extra_af + "," if extra_af else "") + "loudnorm=I=-14:TP=-1:LRA=11:print_format=json"
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        raise RuntimeError("loudnorm measure failed:\n" + p.stderr[-800:])
    return json.loads(m.group(0))


def loudnorm_filter(path, lufs=-14.0, tp=-1.0, lra=11.0, pre=None):
    j = measure(path, pre)
    f = (f"loudnorm=I={lufs}:TP={tp}:LRA={lra}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
         f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    return ((pre + ",") if pre else "") + f + ",aresample=48000"


def has_video(p):
    return media_info(p).get("has_video", False)


def out_maps(inp):
    return ["-map", "0:v?", "-c:v", "copy"] if has_video(inp) else []


def cmd_loudnorm(a):
    af = loudnorm_filter(a.input, a.lufs, a.tp)
    ffmpeg(["-i", a.input, *out_maps(a.input), "-map", "0:a", "-af", af, *ACODEC, "-movflags", "+faststart", a.out])
    j = measure(a.out)
    print(f"wrote {a.out}: {j['input_i']} LUFS, TP {j['input_tp']} dBTP")


def cmd_mix(a):
    inf = media_info(a.input); D = inf["duration"]
    mus = (f"[1:a]atrim=start={a.music_start},asetpts=PTS-STARTPTS,atrim=0:{D:.3f},aformat=sample_rates=48000:channel_layouts=stereo,"
           f"volume={a.music_db}dB,afade=t=in:d={a.fade},afade=t=out:st={max(0, D - a.fade):.3f}:d={a.fade}")
    if inf["has_audio"]:
        fc = [f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voice][sc]", f"{mus}[m]"]
        if a.duck:
            fc.append(f"[m][sc]sidechaincompress=threshold={a.duck_threshold}:ratio={a.duck_ratio}:attack=20:release=400:makeup=1[md]")
        else:
            fc.append("[m]anull[md]")
        fc.append("[voice][md]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[mix]")
    else:
        fc = [f"{mus}[mix]"]
    tmp = Path(a.out).with_suffix(".premix.wav")
    ffmpeg(["-i", a.input, "-i", a.music, "-filter_complex", ";".join(fc), "-map", "[mix]", "-c:a", "pcm_s24le", tmp])
    af = loudnorm_filter(tmp, a.lufs, -1.0)
    ffmpeg(["-i", a.input, "-i", tmp, "-map", "0:v?", "-c:v", "copy", "-map", "1:a", "-af", af, *ACODEC, "-shortest",
            "-movflags", "+faststart", a.out])
    tmp.unlink()
    j = measure(a.out); print(f"wrote {a.out}: {j['input_i']} LUFS (duck={a.duck})")


def gen_sfx():
    SFX_DIR.mkdir(exist_ok=True)
    recipes = {
        "whoosh": "anoisesrc=d=0.6:c=pink:a=0.8,highpass=f=300,lowpass=f=6000,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.35:d=0.25,"
                  "aecho=0.6:0.5:30:0.3",
        "hit": "sine=f=55:d=0.5,volume=2.5,afade=t=out:st=0.02:d=0.48:curve=exp[s];anoisesrc=d=0.12:c=white:a=0.6,afade=t=out:d=0.12[n];[s][n]amix=inputs=2:normalize=0",
        "riser": "anoisesrc=d=2:c=white:a=0.5,highpass=f=800,afade=t=in:d=1.9:curve=qsin,afade=t=out:st=1.9:d=0.1",
        "glitch": "anoisesrc=d=0.25:c=white:a=0.7,acrusher=bits=4:mode=log:aa=1,tremolo=f=30:d=1",
        "pop": "sine=f=900:d=0.09,afade=t=out:d=0.09:curve=exp,volume=1.5",
    }
    for k, r in recipes.items():
        ffmpeg(["-filter_complex", r + ",aformat=sample_rates=48000:channel_layouts=stereo", "-c:a", "pcm_s16le", SFX_DIR / f"{k}.wav"])
    print("sfx:", ", ".join(sorted(p.stem for p in SFX_DIR.glob("*.wav"))))


def cmd_sfx(a):
    if not SFX_DIR.exists(): gen_sfx()
    items = [x.split(":") for x in a.at.split(",")]
    args, fc, labels = ["-i", a.input], [], []
    inf = media_info(a.input)
    for i, (t, name) in enumerate(items, 1):
        f = Path(name) if Path(name).exists() else SFX_DIR / f"{name}.wav"
        args += ["-i", f]
        ms = int(float(t) * 1000)
        fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={a.sfx_db}dB,adelay={ms}|{ms}[s{i}]"); labels.append(f"[s{i}]")
    base = "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[b]" if inf["has_audio"] else f"anullsrc=r=48000:cl=stereo,atrim=0:{inf['duration']:.3f}[b]"
    fc.insert(0, base)
    fc.append(f"[b]{''.join(labels)}amix=inputs={len(labels) + 1}:duration=first:normalize=0,alimiter=limit=0.95[out]")
    ffmpeg([*args, "-filter_complex", ";".join(fc), "-map", "0:v?", "-c:v", "copy", "-map", "[out]", *ACODEC, a.out])
    print(f"wrote {a.out} ({len(items)} sfx)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    l = sp.add_parser("loudnorm"); l.add_argument("input"); l.add_argument("-o", "--out", required=True)
    l.add_argument("--lufs", type=float, default=-14.0); l.add_argument("--tp", type=float, default=-1.0)
    m = sp.add_parser("measure"); m.add_argument("input")
    x = sp.add_parser("mix"); x.add_argument("input"); x.add_argument("--music", required=True); x.add_argument("-o", "--out", required=True)
    x.add_argument("--music-db", type=float, default=-8.0); x.add_argument("--music-start", type=float, default=0.0)
    x.add_argument("--fade", type=float, default=1.0); x.add_argument("--duck", action="store_true")
    x.add_argument("--duck-threshold", type=float, default=0.03); x.add_argument("--duck-ratio", type=float, default=8)
    x.add_argument("--lufs", type=float, default=-14.0)
    s = sp.add_parser("sfx"); s.add_argument("input"); s.add_argument("-o", "--out", required=True); s.add_argument("--at", required=True)
    s.add_argument("--sfx-db", type=float, default=-4.0)
    sp.add_parser("gen-sfx")
    d = sp.add_parser("denoise"); d.add_argument("input"); d.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    if a.cmd == "loudnorm": cmd_loudnorm(a)
    elif a.cmd == "measure":
        j = measure(a.input); print(json.dumps({k: j[k] for k in ("input_i", "input_tp", "input_lra")}))
    elif a.cmd == "mix": cmd_mix(a)
    elif a.cmd == "sfx": cmd_sfx(a)
    elif a.cmd == "gen-sfx": gen_sfx()
    else:
        ffmpeg(["-i", a.input, "-map", "0:v?", "-c:v", "copy", "-map", "0:a", "-af",
                "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-20dB:ratio=3:attack=10:release=200", *ACODEC, a.out])
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
