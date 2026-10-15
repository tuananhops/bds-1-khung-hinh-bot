"""Dialogue cleanup chain: HPF -> denoise (arnndn RNN or afftdn) -> EQ -> de-ess -> compressor -> loudnorm.
vtk clean in.(mp4|wav) -o out [--denoise rnn|fft|none --nr 12 --lufs -14 --voice male|female]"""
import argparse, sys, os; sys.path.insert(0, os.path.dirname(__file__))
from vtk_common import ffmpeg, ACODEC, TOOLKIT
a = argparse.ArgumentParser(); a.add_argument("inp"); a.add_argument("-o", required=True)
a.add_argument("--denoise", default="rnn"); a.add_argument("--nr", type=float, default=12); a.add_argument("--lufs", type=float, default=-14)
a.add_argument("--voice", default="male")
o = a.parse_args()
model = TOOLKIT / "models" / "rnnoise" / "sh.rnnn"
dn = {"rnn": f"arnndn=m='{model}':mix=0.9" if model.exists() else f"afftdn=nr={o.nr}:nf=-40:tn=1",
      "fft": f"afftdn=nr={o.nr}:nf=-40:tn=1", "none": "anull"}[o.denoise]
hp = 80 if o.voice == "male" else 100
chain = ",".join([f"highpass=f={hp}", dn, "equalizer=f=250:t=q:w=1.2:g=-3", "equalizer=f=3500:t=q:w=1:g=2.5",
                  "highshelf=f=10000:g=1.5", "deesser=i=0.4:m=0.5:f=0.5", "acompressor=threshold=-20dB:ratio=3:attack=10:release=120:makeup=3",
                  f"loudnorm=I={o.lufs}:TP=-1.5:LRA=9", "aresample=48000"])
video = o.o.lower().endswith((".mp4", ".mov"))
ffmpeg(["-i", o.inp, "-af", chain, *(["-c:v", "copy"] if video else ["-vn"]), *(ACODEC if video else []), o.o]); print(o.o, "denoise=", dn.split("=")[0])
