#!/usr/bin/env python3
"""Cut a set of clips to the beat of a music track (montage / hype edit).

Examples:
  beat_cut.py --music song.mp3 --clips a.mp4 b.mp4 c.mp4 -o montage.mp4
  beat_cut.py --music song.mp3 --clips raw/ --pattern 2,2,1,1,4 --punch 4 --preset 1080p-9x16 -o reel.mp4
  beat_cut.py --music song.mp3 --clips raw/ --every 2 --start 3.5 --duration 30 --edl cuts.json -o out.mp4

--every N       cut every N beats (default 2)
--pattern       cyclic list of beat counts per shot (overrides --every); e.g. 4,2,2,1,1
--punch K       zoom-punch on the first frames of every K-th shot (0 = off)
--flash K       white flash on every K-th cut (0 = off)
--mode          sequential (walk through each clip) | random (random in-points) | energy (pick high-motion moments)
"""
import argparse, json, random, sys, tempfile
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import ffmpeg, media_info, conform_filter, vcodec, ACODEC, PRESETS

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".mts"}


def get_beats(music, start, duration):
    import librosa
    y, sr = librosa.load(str(music), sr=22050, mono=True)
    oenv = librosa.onset.onset_strength(y=y, sr=sr)
    tempo, frames = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, trim=False)
    beats = librosa.frames_to_time(frames, sr=sr)
    total = len(y) / sr
    end = min(total, start + duration) if duration else total
    beats = [b for b in beats if start <= b <= end]
    return float(np.atleast_1d(tempo)[0]), beats, end


def motion_peaks(clip, n=40):
    """Return candidate in-points (sec) sorted by motion energy (for --mode energy)."""
    import cv2
    cap = cv2.VideoCapture(str(clip)); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); scores = []
    for i in np.linspace(0, max(cnt - 3, 0), n).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok1, a = cap.read(); ok2, b = cap.read()
        if ok1 and ok2:
            a = cv2.cvtColor(cv2.resize(a, (160, 90)), cv2.COLOR_BGR2GRAY); b = cv2.cvtColor(cv2.resize(b, (160, 90)), cv2.COLOR_BGR2GRAY)
            scores.append((float(np.mean(cv2.absdiff(a, b))), i / fps))
    cap.release()
    return [t for _, t in sorted(scores, reverse=True)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--music", required=True); ap.add_argument("--clips", nargs="+", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--every", type=int, default=2); ap.add_argument("--pattern", default=None)
    ap.add_argument("--start", type=float, default=0.0, help="music start offset (s)")
    ap.add_argument("--duration", type=float, default=None, help="max output length (s)")
    ap.add_argument("--preset", default="1080p-9x16", choices=PRESETS.keys())
    ap.add_argument("--fit", default="cover", choices=["cover", "fit", "blur"])
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--mode", default="sequential", choices=["sequential", "random", "energy"])
    ap.add_argument("--punch", type=int, default=0); ap.add_argument("--flash", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--edl", default=None, help="write cut list JSON")
    ap.add_argument("--fast", action="store_true", help="fast encode for previews")
    a = ap.parse_args()
    random.seed(a.seed)

    clips = []
    for c in a.clips:
        p = Path(c)
        clips += sorted(x for x in p.iterdir() if x.suffix.lower() in VIDEO_EXT) if p.is_dir() else [p]
    if not clips:
        sys.exit("no clips")
    infos = {c: media_info(c) for c in clips}
    tempo, beats, end = get_beats(a.music, a.start, a.duration)
    if len(beats) < 2:
        sys.exit("not enough beats detected")
    pattern = [int(x) for x in a.pattern.split(",")] if a.pattern else [a.every]
    # cut points on beats; first segment starts at a.start (music offset) to keep sync
    cut_pts, bi, k = [a.start], 0, 0
    # snap first beat: begin exactly on first beat if it is close
    if beats[0] - a.start < 0.25:
        cut_pts = [beats[0]]
    while True:
        bi += pattern[k % len(pattern)]; k += 1
        if bi >= len(beats):
            break
        cut_pts.append(beats[bi])
    if end - cut_pts[-1] > 0.3:
        cut_pts.append(end)
    music_start = cut_pts[0]
    W, H = PRESETS[a.preset]; fps = a.fps
    # frame-accurate durations from cumulative positions
    frames_at = [round((t - music_start) * fps) for t in cut_pts]
    seg_frames = [b - a_ for a_, b in zip(frames_at, frames_at[1:]) if b - a_ > 0]

    cursor = {c: 0.0 for c in clips}
    energy = {c: motion_peaks(c) for c in clips} if a.mode == "energy" else {}
    edl = []
    with tempfile.TemporaryDirectory() as td:
        segs = []
        for i, nf in enumerate(seg_frames):
            clip = clips[i % len(clips)]; inf = infos[clip]; dur = nf / fps
            vdur = inf.get("vduration", inf["duration"])
            maxin = max(0.0, vdur - dur - 0.05)
            if a.mode == "random":
                tin = random.uniform(0, maxin)
            elif a.mode == "energy" and energy.get(clip):
                tin = min(energy[clip].pop(0), maxin) if energy[clip] else random.uniform(0, maxin)
            else:
                tin = cursor[clip] if cursor[clip] <= maxin else 0.0
                cursor[clip] = tin + dur
            vf = conform_filter(W, H, a.fit, fps)
            if a.punch and i % a.punch == 0 and i > 0:
                vf += (f",scale=w='trunc({W}*(1+0.15*max(0,1-t/0.22))/2)*2':h='trunc({H}*(1+0.15*max(0,1-t/0.22))/2)*2':eval=frame,"
                       f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2")
            if a.flash and i % a.flash == 0 and i > 0:
                vf += ",eq=brightness='0.6*max(0,1-t/0.12)':eval=frame"
            seg = Path(td) / f"seg{i:04d}.mp4"
            ffmpeg(["-ss", f"{tin:.3f}", "-i", clip, "-an", "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-frames:v", str(nf), "-r", str(fps),
                    *vcodec(True if a.fast else False), seg])
            segs.append(seg)
            edl.append({"index": i, "clip": str(clip), "in": round(tin, 3), "dur": round(dur, 3),
                        "timeline_start": round(sum(seg_frames[:i]) / fps, 3)})
        lst = Path(td) / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        total = sum(seg_frames) / fps
        ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-ss", f"{music_start:.3f}", "-t", f"{total:.3f}", "-i", a.music,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", *ACODEC,
                "-af", f"afade=t=out:st={max(0, total - 0.6):.3f}:d=0.6", "-shortest", "-movflags", "+faststart", a.out])
    if a.edl:
        Path(a.edl).write_text(json.dumps({"tempo": tempo, "music": a.music, "music_start": music_start, "fps": fps,
                                           "shots": edl}, indent=2))
    print(f"wrote {a.out}: {len(seg_frames)} shots, {total:.2f}s, tempo {tempo:.1f} BPM")


if __name__ == "__main__":
    main()
