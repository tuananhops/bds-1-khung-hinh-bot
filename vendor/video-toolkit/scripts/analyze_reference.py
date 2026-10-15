#!/usr/bin/env python3
"""Analyze a reference video and emit a JSON "edit brief".

Measures: scene cuts + shot lengths, pacing (cuts/min), music tempo + beat grid,
cut-to-beat alignment, loudness (LUFS), colour stats (brightness, contrast,
saturation, warmth, Lab mean/std for colour matching), motion energy, aspect.
Optionally writes a contact sheet of one frame per shot (--contact-sheet).

Usage:
  analyze_reference.py ref.mp4 -o ref_brief.json [--contact-sheet ref_sheet.jpg] [--threshold 27]
"""
import argparse, json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import media_info, ffmpeg, run


def detect_scenes(path, threshold):
    from scenedetect import detect, ContentDetector
    scenes = detect(str(path), ContentDetector(threshold=threshold, min_scene_len=8), show_progress=False)
    sec = lambda x: x.seconds if hasattr(type(x), "seconds") else x.get_seconds()
    return [(sec(s), sec(e)) for s, e in scenes]


def audio_analysis(path, info):
    if not info["has_audio"]:
        return None
    import librosa
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        ffmpeg(["-i", path, "-vn", "-ac", "1", "-ar", "22050", wav])
        y, sr = librosa.load(str(wav), sr=22050, mono=True)
    if len(y) < sr:  # < 1s
        return None
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    beat_t = librosa.frames_to_time(beats, sr=sr).tolist()
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time").tolist()
    rms = librosa.feature.rms(y=y)[0]
    # energy curve (per second) to locate drops/high-energy sections
    hop_t = 512 / sr
    per_sec = int(round(1 / hop_t))
    energy = [float(np.mean(rms[i:i + per_sec])) for i in range(0, len(rms), per_sec)]
    emax = max(energy) or 1
    energy = [round(e / emax, 3) for e in energy]
    peak_secs = [i for i, e in enumerate(energy) if e >= 0.85]
    return {"tempo_bpm": round(tempo, 2), "beat_count": len(beat_t), "beats": [round(b, 3) for b in beat_t],
            "onsets": [round(o, 3) for o in onsets[:2000]], "energy_per_sec": energy,
            "high_energy_seconds": peak_secs}


def loudness(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
                        "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))
    return {"integrated_lufs": float(j["input_i"]), "true_peak_db": float(j["input_tp"]), "lra": float(j["input_lra"])}


def colour_motion(path, info, samples=120):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or int(info["duration"] * info["fps"])
    idxs = np.linspace(0, max(n - 2, 0), min(samples, max(n - 1, 1))).astype(int)
    L, C, S, labm, labs, warm, motion = [], [], [], [], [], [], []
    prev = None
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if not ok:
            continue
        f = cv2.resize(f, (320, int(320 * f.shape[0] / f.shape[1])))
        lab = cv2.cvtColor(f, cv2.COLOR_BGR2LAB).astype(np.float32)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.float32)
        l = lab[..., 0] * 100 / 255
        L.append(l.mean()); C.append(l.std()); S.append(hsv[..., 1].mean() / 255)
        labm.append(lab.reshape(-1, 3).mean(0)); labs.append(lab.reshape(-1, 3).std(0))
        warm.append(float(lab[..., 2].mean() - 128))  # +b = yellow/warm
        # motion: diff vs next frame
        ok2, g = cap.read()
        if ok2:
            g = cv2.resize(g, (f.shape[1], f.shape[0]))
            motion.append(float(np.mean(cv2.absdiff(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)))))
    cap.release()
    if not L:
        return None
    labm, labs = np.mean(labm, 0), np.mean(labs, 0)
    return {
        "brightness_L_mean": round(float(np.mean(L)), 2),
        "contrast_L_std": round(float(np.mean(C)), 2),
        "saturation_mean": round(float(np.mean(S)), 3),
        "warmth_b_mean": round(float(np.mean(warm)), 2),
        "tint_a_mean": round(float(labm[1] - 128), 2),
        "lab_mean_opencv": [round(float(x), 3) for x in labm],
        "lab_std_opencv": [round(float(x), 3) for x in labs],
        "motion_energy": round(float(np.mean(motion)) if motion else 0.0, 2),
        "brightness_timeline": [round(float(x), 1) for x in L],
    }


def describe(b):
    tips = []
    p = b["pacing"]
    if p["avg_shot_len_s"]:
        s = p["avg_shot_len_s"]
        tips.append(f"Pacing: avg shot {s:.2f}s ({p['cuts_per_min']:.0f} cuts/min) -> "
                    + ("very fast / hype edit" if s < 1.2 else "fast social edit" if s < 2.5 else "medium" if s < 5 else "slow / cinematic"))
    a = b.get("audio")
    if a:
        bl = 60 / a["tempo_bpm"] if a["tempo_bpm"] else None
        if bl and p["avg_shot_len_s"]:
            tips.append(f"Music {a['tempo_bpm']:.0f} BPM (beat={bl:.2f}s); avg shot ~= {p['avg_shot_len_s']/bl:.1f} beats -> use beat_cut.py --every {max(1, round(p['avg_shot_len_s']/bl))}")
        if b.get("cut_beat_alignment") is not None:
            tips.append(f"{b['cut_beat_alignment']*100:.0f}% of cuts land within 80ms of a beat" + (" -> edit is beat-synced" if b["cut_beat_alignment"] > 0.5 else ""))
    c = b.get("colour")
    if c:
        tone = "warm" if c["warmth_b_mean"] > 6 else "cool" if c["warmth_b_mean"] < -2 else "neutral"
        sat = "punchy/saturated" if c["saturation_mean"] > 0.45 else "desaturated/filmic" if c["saturation_mean"] < 0.22 else "natural saturation"
        con = "high contrast" if c["contrast_L_std"] > 25 else "low contrast/flat" if c["contrast_L_std"] < 14 else "medium contrast"
        tips.append(f"Look: {tone}, {sat}, {con}, brightness L={c['brightness_L_mean']} -> color_grade.py match --ref <this video>")
    if b.get("loudness"):
        tips.append(f"Loudness {b['loudness']['integrated_lufs']} LUFS (target -14 for social)")
    return tips


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--threshold", type=float, default=27.0, help="ContentDetector threshold (lower=more cuts)")
    ap.add_argument("--contact-sheet", default=None, help="write JPG grid with one frame per shot")
    ap.add_argument("--no-beats-list", action="store_true", help="omit full beat list from JSON")
    a = ap.parse_args()
    info = media_info(a.video)
    scenes = detect_scenes(a.video, a.threshold)
    if not scenes:
        scenes = [(0.0, info["duration"])]
    lens = [e - s for s, e in scenes]
    cuts = [s for s, _ in scenes[1:]]
    brief = {
        "file": str(Path(a.video).resolve()),
        "duration_s": round(info["duration"], 3),
        "resolution": [info.get("width"), info.get("height")], "fps": round(info.get("fps", 0), 3),
        "aspect": "9:16 vertical" if info.get("height", 0) > info.get("width", 1) else "16:9 horizontal" if info.get("width", 0) / max(info.get("height", 1), 1) > 1.5 else "square-ish",
        "pacing": {
            "shot_count": len(scenes),
            "avg_shot_len_s": round(float(np.mean(lens)), 3) if lens else None,
            "median_shot_len_s": round(float(np.median(lens)), 3) if lens else None,
            "min_shot_len_s": round(float(min(lens)), 3), "max_shot_len_s": round(float(max(lens)), 3),
            "cuts_per_min": round(len(cuts) / max(info["duration"], 1e-6) * 60, 2),
        },
        "shots": [{"start": round(s, 3), "end": round(e, 3), "len": round(e - s, 3)} for s, e in scenes],
        "cuts": [round(c, 3) for c in cuts],
    }
    brief["audio"] = audio_analysis(a.video, info)
    if brief["audio"] and cuts and brief["audio"]["beats"]:
        beats = np.array(brief["audio"]["beats"])
        brief["cut_beat_alignment"] = round(float(np.mean([np.min(np.abs(beats - c)) < 0.08 for c in cuts])), 3)
    else:
        brief["cut_beat_alignment"] = None
    brief["loudness"] = loudness(a.video) if info["has_audio"] else None
    brief["colour"] = colour_motion(a.video, info)
    if a.no_beats_list and brief["audio"]:
        brief["audio"].pop("beats"); brief["audio"].pop("onsets")
    brief["recommendations"] = describe(brief)

    if a.contact_sheet:
        with tempfile.TemporaryDirectory() as td:
            frames = []
            for i, (s, e) in enumerate(scenes[:60]):
                f = Path(td) / f"s{i:03d}.jpg"
                ffmpeg(["-ss", f"{(s + e) / 2:.3f}", "-i", a.video, "-frames:v", "1", "-vf", "scale=320:-2", f])
                frames.append(str(f))
            run(["montage", *frames, "-tile", "6x", "-geometry", "+4+4", "-background", "#111", a.contact_sheet])
        brief["contact_sheet"] = str(Path(a.contact_sheet).resolve())

    out = json.dumps(brief, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}")
    else:
        print(out)
    for t in brief["recommendations"]:
        print(" *", t, file=sys.stderr)


if __name__ == "__main__":
    main()
