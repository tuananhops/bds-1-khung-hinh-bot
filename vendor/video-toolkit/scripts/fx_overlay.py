"""Helper: composite python-rendered RGBA frames over a base video in one ffmpeg pass."""
import subprocess, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from vtk_common import vcodec, ACODEC, media_info
def composite(base, out, render_frame, fps=30, size=None, blend=None):
    mi = media_info(base); W, H = size or (mi["width"], mi["height"]); n = int(mi["duration"] * fps)
    ov = "[0:v]fps=%d,format=yuv420p[b];[1:v]format=rgba[o];" % fps
    ov += ("[b]format=gbrp[b2];[o]format=gbrp[o2];[b2][o2]blend=all_mode=%s,format=yuv420p[v]" % blend) if blend else "[b][o]overlay=0:0:shortest=1,format=yuv420p[v]"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", base, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-filter_complex", ov, "-map", "[v]", "-map", "0:a?", *vcodec(), *ACODEC, "-shortest", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n): p.stdin.write(render_frame(i / fps, W, H).tobytes())
    p.stdin.close(); assert p.wait() == 0, "ffmpeg failed"; return out
