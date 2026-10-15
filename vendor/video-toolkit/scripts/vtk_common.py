"""Shared helpers for the video toolkit (ffmpeg wrappers, probing, presets)."""
import json, os, shlex, subprocess, sys
from pathlib import Path

TOOLKIT = Path(__file__).resolve().parent.parent
FONTS_DIR = TOOLKIT / "fonts"
LUTS_DIR = TOOLKIT / "luts"

# H.264 high-quality defaults
VCODEC = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
          "-profile:v", "high", "-movflags", "+faststart"]
VCODEC_FAST = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
ACODEC = ["-c:a", "aac", "-b:a", "320k", "-ar", "48000"]

PRESETS = {
    "1080p-16x9": (1920, 1080),
    "1080p-9x16": (1080, 1920),
    "4k-16x9": (3840, 2160),
    "4k-9x16": (2160, 3840),
    "1080p-1x1": (1080, 1080),
    "1080p-4x5": (1080, 1350),
}


def vcodec(fast=False):
    if fast or os.environ.get("VTK_FAST"):
        return list(VCODEC_FAST)
    return list(VCODEC)


def run(cmd, quiet=True):
    """Run a command list; raise with stderr tail on failure."""
    if not quiet or os.environ.get("VTK_DEBUG"):
        print("+", " ".join(shlex.quote(str(c)) for c in cmd), file=sys.stderr)
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(map(str, cmd[:6]))} ...\n{tail}")
    return p


def ffmpeg(args, quiet=True):
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], quiet=quiet)


def probe(path):
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(p.stdout)


def media_info(path):
    d = probe(path)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    info = {"duration": float(d["format"].get("duration", 0) or 0), "has_audio": a is not None,
            "has_video": v is not None}
    if v:
        num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
        fps = float(num) / float(den) if float(den) else 30.0
        info.update(width=int(v["width"]), height=int(v["height"]), fps=fps or 30.0)
        if v.get("duration"):
            info["vduration"] = float(v["duration"])
    return info


def has_audio(path):
    return media_info(path)["has_audio"]


def ass_escape_path(p):
    """Escape a path for use inside an ffmpeg filter argument (subtitles=/ass=/lut3d=)."""
    s = str(Path(p).resolve())
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")


def font_file(name="BeVietnamPro-Bold"):
    for ext in (".ttf", ".otf"):
        f = FONTS_DIR / f"{name}{ext}"
        if f.exists():
            return f
    hits = sorted(FONTS_DIR.glob(f"{name}*"))
    if hits:
        return hits[0]
    raise FileNotFoundError(f"font {name} not in {FONTS_DIR}")


def conform_filter(w, h, mode="cover", fps=30):
    """Filter-chain string that makes any input exactly WxH @fps.
    cover = scale+center crop (fills frame); fit = letterbox black; blur = fit over blurred fill (good for 16:9 -> 9:16)."""
    if mode == "cover":
        f = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
    elif mode == "fit":
        f = f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
    elif mode == "blur":
        f = (f"split=2[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=40,eq=brightness=-0.08[bgb];"
             f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos[fgs];[bgb][fgs]overlay=(W-w)/2:(H-h)/2")
    else:
        raise ValueError(mode)
    return f"{f},setsar=1,fps={fps},format=yuv420p"


# Platform safe zones for 1080x1920 (px kept clear of UI: captions/buttons/profile).
# "all" = union of TikTok/Reels/Shorts so one export is safe everywhere.
SAFE_ZONES_9x16 = {
    "tiktok": dict(top=160, bottom=480, left=60, right=150),
    "reels":  dict(top=220, bottom=420, left=60, right=130),
    "shorts": dict(top=180, bottom=400, left=60, right=150),
    "all":    dict(top=220, bottom=480, left=60, right=150),
}


def safe_zone(w, h, platform="all"):
    """Scale 1080x1920 safe margins to WxH. Horizontal (16:9) gets a generic 5% title-safe."""
    if h > w:
        z = SAFE_ZONES_9x16.get(platform, SAFE_ZONES_9x16["all"])
        sx, sy = w / 1080, h / 1920
        return {k: int(v * (sx if k in ("left", "right") else sy)) for k, v in z.items()}
    return dict(top=int(h * .06), bottom=int(h * .08), left=int(w * .05), right=int(w * .05))


def ass_color(hex_rgb, alpha=0):
    """'#RRGGBB' -> ASS &HAABBGGRR"""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t):
    t = max(0, t); cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def ass_header(w, h, styles):
    s = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
         "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "", "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
         "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    s += styles
    s += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    return "\n".join(s) + "\n"


def burn_ass(inp, ass, out, fast=False, extra_vf=None):
    vf = f"ass='{ass_escape_path(ass)}':fontsdir='{ass_escape_path(FONTS_DIR)}'"
    if extra_vf:
        vf = f"{extra_vf},{vf}"
    ffmpeg(["-i", inp, "-filter_complex", f"[0:v]{vf},format=yuv420p[v]", "-map", "[v]", "-map", "0:a?",
            "-c:a", "copy", *vcodec(fast), out])
