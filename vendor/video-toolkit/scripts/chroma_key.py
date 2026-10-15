"""Chroma key (green/blue screen) + despill, composite over a background video/image.
vtk key fg.mp4 -b bg.mp4 -o out.mp4 [--color 0x00FF00 --sim 0.12 --blend 0.08 --scale 0.8 --x center --y bottom]"""
import argparse, sys; sys.path.insert(0, __import__('os').path.dirname(__file__))
from vtk_common import ffmpeg, vcodec, ACODEC, media_info
a = argparse.ArgumentParser(); a.add_argument("fg"); a.add_argument("-b", "--bg", required=True); a.add_argument("-o", required=True)
a.add_argument("--color", default="0x00FF00"); a.add_argument("--sim", type=float, default=0.12); a.add_argument("--blend", type=float, default=0.08)
a.add_argument("--scale", type=float, default=1.0); a.add_argument("--x", default="(W-w)/2"); a.add_argument("--y", default="H-h")
a.add_argument("--W", type=int, default=1080); a.add_argument("--H", type=int, default=1920)
o = a.parse_args()
spill = "green" if o.color.lower().endswith("ff00") else "blue"
bgimg = o.bg.lower().endswith((".jpg", ".png", ".jpeg"))
d = media_info(o.fg)["duration"]
bgin = ["-loop", "1", "-t", str(d), "-i", o.bg] if bgimg else ["-stream_loop", "-1", "-i", o.bg]
fc = (f"[1:v]scale={o.W}:{o.H}:force_original_aspect_ratio=increase,crop={o.W}:{o.H},setsar=1,fps=30[bg];"
      f"[0:v]format=yuv444p,chromakey={o.color}:{o.sim}:{o.blend},despill=type={spill}:mix=0.5:expand=0.1,"
      f"scale=iw*{o.scale}*{o.W}/iw:-2,format=yuva420p[fg];[bg][fg]overlay=x={o.x}:y={o.y}:shortest=1,format=yuv420p[v]")
ffmpeg(["-i", o.fg, *bgin, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?", "-t", str(d), *vcodec(), *ACODEC, o.o]); print(o.o)
