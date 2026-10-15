"""2-pass vid.stab stabilization. vtk stab in.mp4 -o out.mp4 [--shakiness 6 --smoothing 15 --zoom 0]"""
import argparse, sys, os, tempfile; sys.path.insert(0, os.path.dirname(__file__))
from vtk_common import ffmpeg, vcodec, ACODEC
a = argparse.ArgumentParser(); a.add_argument("inp"); a.add_argument("-o", required=True)
a.add_argument("--shakiness", type=int, default=6); a.add_argument("--smoothing", type=int, default=15); a.add_argument("--zoom", type=float, default=0)
o = a.parse_args(); trf = tempfile.mktemp(suffix=".trf")
ffmpeg(["-i", o.inp, "-vf", f"vidstabdetect=shakiness={o.shakiness}:accuracy=15:result={trf}", "-f", "null", "-"])
ffmpeg(["-i", o.inp, "-vf", f"vidstabtransform=input={trf}:smoothing={o.smoothing}:optzoom=1:zoom={o.zoom}:interpol=bicubic,unsharp=5:5:0.6:3:3:0.3",
        "-map", "0:v", "-map", "0:a?", *vcodec(), *ACODEC, o.o]); os.remove(trf); print(o.o)
