#!/usr/bin/env python3
"""Final delivery render with platform presets. DEFAULT = 1080x1920 9:16 (TikTok/Reels/Shorts).

  render.py in.mp4 -o final.mp4                          # preset 'vertical' (1080x1920, 30fps)
  render.py in.mp4 -o tiktok.mp4 --preset tiktok --fps 60
  render.py in_16x9.mp4 -o v.mp4 --reframe smart         # face/subject-tracked 16:9 -> 9:16
  render.py in.mp4 -o yt.mp4 --preset youtube            # 1920x1080 16:9
  render.py in.mp4 --all-platforms -o out_dir/           # tiktok + reels + shorts in one go
  render.py --list
All presets: H.264 High, CRF 18, yuv420p, BT.709 tags, GOP 2s, AAC 320k 48kHz, 2-pass loudnorm -14 LUFS / -1 dBTP.
--reframe (when aspect differs): smart (tracking) | center (crop) | blur (fit on blurred bg) | fit (letterbox)
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import ffmpeg, media_info, conform_filter, ACODEC
import audio as audio_mod

HERE = Path(__file__).resolve().parent
PLATFORM_PRESETS = {
    # name: (W, H, default fps, maxrate, note)
    "vertical": (1080, 1920, 30, "25M", "default 9:16 for all short-form platforms"),
    "tiktok":   (1080, 1920, 30, "25M", "TikTok 9:16; 30 or 60 fps"),
    "reels":    (1080, 1920, 30, "25M", "Instagram Reels 9:16; 30 or 60 fps"),
    "shorts":   (1080, 1920, 30, "25M", "YouTube Shorts 9:16; 30 or 60 fps"),
    "4k-vertical": (2160, 3840, 30, "60M", "4K 9:16 master"),
    "youtube":  (1920, 1080, 30, "25M", "YouTube 16:9 1080p"),
    "4k-16x9":  (3840, 2160, 30, "60M", "4K UHD 16:9"),
    "square":   (1080, 1080, 30, "20M", "1:1 feed"),
    "portrait-4x5": (1080, 1350, 30, "20M", "4:5 IG feed"),
    "1080p-9x16": (1080, 1920, 30, "25M", "alias of vertical"),
    "1080p-16x9": (1920, 1080, 30, "25M", "alias of youtube"),
}


def encode(inp, out, W, H, fps, maxrate, reframe, lufs, crf=18, preset="slow", no_loudnorm=False):
    inf = media_info(inp)
    src = inp; tmpdir = tempfile.TemporaryDirectory()
    same_aspect = abs(inf["width"] / inf["height"] - W / H) < 0.01
    if not same_aspect and reframe == "smart":
        src = Path(tmpdir.name) / "reframed.mp4"
        r = subprocess.run([sys.executable, HERE / "reframe.py", inp, "-o", src, "--size", f"{W}x{H}", "--fps", str(fps), "--fast"],
                           capture_output=True, text=True)
        if r.returncode: raise RuntimeError(r.stderr[-1500:])
    mode = {"smart": "cover", "center": "cover", "blur": "blur", "fit": "fit"}[reframe]
    vf = conform_filter(W, H, mode, fps)
    level = "5.2" if W * H > 1920 * 1088 or fps > 30 and W * H > 1920 * 1088 else "4.2"
    v = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-level:v", level,
         "-pix_fmt", "yuv420p", "-maxrate", maxrate, "-bufsize", str(int(maxrate[:-1]) * 2) + "M",
         "-g", str(fps * 2), "-keyint_min", str(fps), "-sc_threshold", "40", "-bf", "2",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart"]
    has_a = media_info(src)["has_audio"]
    a = []
    if has_a:
        a = ["-map", "0:a:0", *ACODEC]
        if not no_loudnorm:
            a += ["-af", audio_mod.loudnorm_filter(src, lufs, -1.0)]
    else:
        # platforms prefer an audio track: add silent stereo
        a = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    if has_a:
        ffmpeg(["-i", src, "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", *a, *v, out])
    else:
        ffmpeg(["-i", src, *a, "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a", *ACODEC, "-shortest", *v, out])
    tmpdir.cleanup()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?"); ap.add_argument("-o", "--out")
    ap.add_argument("--preset", default="vertical", choices=PLATFORM_PRESETS.keys())
    ap.add_argument("--fps", type=int, choices=[24, 25, 30, 50, 60]); ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--reframe", default="smart", choices=["smart", "center", "blur", "fit"])
    ap.add_argument("--lufs", type=float, default=-14.0); ap.add_argument("--no-loudnorm", action="store_true")
    ap.add_argument("--x264-preset", default="slow"); ap.add_argument("--all-platforms", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, (w, h, f, m, n) in PLATFORM_PRESETS.items(): print(f"{k:14s} {w}x{h} {f}fps maxrate {m}  - {n}")
        return
    if not a.input or not a.out: ap.error("input and -o required")
    jobs = [(p, Path(a.out) / f"{Path(a.input).stem}_{p}.mp4") for p in ("tiktok", "reels", "shorts")] if a.all_platforms else [(a.preset, Path(a.out))]
    if a.all_platforms: Path(a.out).mkdir(parents=True, exist_ok=True)
    for p, out in jobs:
        W, H, fps, mr, _ = PLATFORM_PRESETS[p]
        encode(a.input, out, W, H, a.fps or fps, mr, a.reframe, a.lufs, a.crf, a.x264_preset, a.no_loudnorm)
        i = media_info(out)
        print(f"wrote {out}: {i['width']}x{i['height']} @{i['fps']:.0f}fps {i['duration']:.2f}s [{p}]")


if __name__ == "__main__":
    main()
