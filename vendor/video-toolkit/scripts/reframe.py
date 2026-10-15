#!/usr/bin/env python3
"""Smart reframe (e.g. 16:9 -> 9:16) with subject tracking.

  reframe.py in.mp4 -o vertical.mp4                         # auto: face -> motion -> center, 1080x1920
  reframe.py in.mp4 -o v.mp4 --mode face --smooth 0.9       # YuNet face tracking (OpenCV DNN)
  reframe.py in.mp4 -o v.mp4 --mode center
  reframe.py in.mp4 -o v.mp4 --mode blur                    # no crop: fit over blurred background
  reframe.py in.mp4 -o sq.mp4 --size 1080x1080
Tracking path is smoothed (EMA + dead-zone + max pan speed) so the virtual camera moves like an operator,
and re-centres hard on scene cuts. --debug writes the path JSON.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np, cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import media_info, ffmpeg, conform_filter, vcodec, ACODEC, TOOLKIT

YUNET = TOOLKIT / "models" / "face_detection_yunet_2023mar.onnx"


class Detector:
    def __init__(self, mode):
        self.mode = mode; self.face = None; self.prev = None
        if mode in ("auto", "face") and YUNET.exists():
            self.face = cv2.FaceDetectorYN.create(str(YUNET), "", (320, 320), 0.6, 0.3, 5000)

    def __call__(self, frame):
        """Return (x_center_norm, confidence_kind) for this frame, or None."""
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (480, int(h * 480 / w)))
        if self.face is not None:
            big = cv2.resize(frame, (960, int(h * 960 / w))) if w > 960 else frame
            self.face.setInputSize((big.shape[1], big.shape[0]))
            _, faces = self.face.detect(big)
            if faces is not None and len(faces):
                # weight by area*score -> follow the dominant face (or group centroid)
                wts = faces[:, 2] * faces[:, 3] * faces[:, 14]
                cx = float(np.sum((faces[:, 0] + faces[:, 2] / 2) * wts) / np.sum(wts)) / big.shape[1]
                return cx, "face"
        if self.mode in ("auto", "motion"):
            g = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (9, 9), 0)
            prev, self.prev = self.prev, g
            if prev is not None:
                d = cv2.absdiff(g, prev).astype(np.float32)
                d[d < 12] = 0
                col = d.sum(0)
                if col.sum() > d.size * 0.4:
                    return float(np.sum(np.arange(len(col)) * col) / col.sum()) / len(col), "motion"
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--size", default="1080x1920"); ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--mode", default="auto", choices=["auto", "face", "motion", "center", "blur"])
    ap.add_argument("--smooth", type=float, default=0.92, help="EMA factor 0..0.99 (higher = steadier)")
    ap.add_argument("--max-speed", type=float, default=0.012, help="max pan per frame (fraction of width)")
    ap.add_argument("--deadzone", type=float, default=0.04); ap.add_argument("--detect-every", type=int, default=3)
    ap.add_argument("--debug"); ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    W, H = map(int, a.size.lower().split("x"))
    inf = media_info(a.input); fps = a.fps or round(inf["fps"])
    if a.mode in ("center", "blur"):
        ffmpeg(["-i", a.input, "-filter_complex", f"[0:v]{conform_filter(W, H, 'cover' if a.mode == 'center' else 'blur', fps)}[v]",
                "-map", "[v]", "-map", "0:a?", *ACODEC, *vcodec(a.fast), a.out])
        print(f"wrote {a.out} ({a.mode})"); return
    iw, ih = inf["width"], inf["height"]
    # crop window in source pixels with target aspect
    if iw / ih > W / H:
        ch, cw = ih, int(round(ih * W / H)) // 2 * 2
    else:
        cw, ch = iw, int(round(iw * H / W)) // 2 * 2
    # pass 1: detections
    cap = cv2.VideoCapture(str(a.input)); det = Detector(a.mode)
    raw, kinds, i, prevhist = [], [], 0, None
    cuts = set()
    while True:
        ok, f = cap.read()
        if not ok: break
        hist = cv2.calcHist([cv2.cvtColor(cv2.resize(f, (160, 90)), cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        if prevhist is not None and cv2.compareHist(prevhist, hist, cv2.HISTCMP_CORREL) < 0.6:
            cuts.add(i)
        prevhist = hist
        r = det(f) if (i % a.detect_every == 0 or i in cuts) else None
        raw.append(r[0] if r else None); kinds.append(r[1] if r else None); i += 1
    cap.release()
    n = len(raw)
    # fill gaps (hold last, else centre), then smooth
    target = np.full(n, 0.5); last = None
    for k in range(n):
        if k in cuts: last = None
        if raw[k] is not None: last = raw[k]
        target[k] = last if last is not None else np.nan
    # back-fill segments that start with no detection
    for k in range(n - 2, -1, -1):
        if np.isnan(target[k]) and (k + 1) not in cuts: target[k] = target[k + 1]
    target = np.where(np.isnan(target), 0.5, target)
    half = cw / 2 / iw
    path = np.zeros(n); pos = target[0]
    for k in range(n):
        if k in cuts:
            pos = target[k]
        elif abs(target[k] - pos) > a.deadzone:
            step = (1 - a.smooth) * (target[k] - pos)
            pos += float(np.clip(step, -a.max_speed, a.max_speed))
        path[k] = np.clip(pos, half, 1 - half)
    xs = np.round(path * iw - cw / 2).astype(int).clip(0, iw - cw)
    if a.debug:
        Path(a.debug).write_text(json.dumps({"crop": [cw, ch], "cuts": sorted(cuts), "x": xs.tolist(), "kinds": kinds}))
    # pass 2: crop + pipe raw frames to ffmpeg, mux original audio
    y0 = (ih - ch) // 2
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{cw}x{ch}", "-r", str(inf["fps"]), "-i", "-", "-i", str(a.input),
                            "-map", "0:v", "-map", "1:a?", "-vf", f"scale={W}:{H}:flags=lanczos,setsar=1,fps={fps},format=yuv420p",
                            *vcodec(a.fast), *ACODEC, "-shortest", str(a.out)], stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(str(a.input)); k = 0
    while True:
        ok, f = cap.read()
        if not ok: break
        x = xs[min(k, n - 1)]
        enc.stdin.write(np.ascontiguousarray(f[y0:y0 + ch, x:x + cw]).tobytes()); k += 1
    cap.release(); enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg encode failed")
    fk = sum(1 for x in kinds if x == "face"); mk = sum(1 for x in kinds if x == "motion")
    print(f"wrote {a.out}: {W}x{H}, crop {cw}x{ch}, {len(cuts)} cuts, detections face={fk} motion={mk}")


if __name__ == "__main__":
    main()
