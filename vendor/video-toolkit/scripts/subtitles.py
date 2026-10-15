#!/usr/bin/env python3
"""Auto subtitles: faster-whisper transcription -> styled, safe-zone-aware ASS -> burn-in.
Full Vietnamese support (Be Vietnam Pro font, UTF-8, diacritics-safe uppercase).

  subtitles.py transcribe in.mp4 -o words.json [--model small --language vi]
  subtitles.py style words.json --video in.mp4 -o subs.ass [--style tiktok --platform all --position lower]
  subtitles.py burn in.mp4 subs.ass -o out.mp4
  subtitles.py auto in.mp4 -o out.mp4 [--language vi --style tiktok --model small]   # all three steps
  subtitles.py style subs.srt --video in.mp4 -o subs.ass     # style an existing SRT instead of whisper

Styles: tiktok (2-4 words, big bold uppercase, active word highlighted + pop),
        karaoke (line with word-by-word colour sweep), clean (sentence lines, outline),
        boxed (sentence lines on semi-transparent box), minimal (small lower text).
Positions: lower (above platform UI), middle, upper. --platform tiktok|reels|shorts|all picks safe margins.
"""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import media_info, ass_header, ass_time, ass_color, safe_zone, burn_ass, ffmpeg

FONTS = {"vi": "Be Vietnam Pro", "default": "Montserrat"}


def transcribe(video, model="small", language=None, device="cpu", compute="float32"):
    from faster_whisper import WhisperModel
    import subprocess, numpy as np
    # decode with system ffmpeg (avoids PyAV version issues), 16 kHz mono float32
    pcm = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.float32).copy()
    m = WhisperModel(model, device=device, compute_type=compute, cpu_threads=0)
    segs, info = m.transcribe(audio, language=language, word_timestamps=True, vad_filter=True, beam_size=5,
                              condition_on_previous_text=False, vad_parameters={"min_silence_duration_ms": 300})
    words, segments = [], []
    for s in segs:
        # drop likely hallucinations (music/noise mistaken for speech)
        if (s.no_speech_prob > 0.5 and s.avg_logprob < -0.7) or s.avg_logprob < -1.2 or s.compression_ratio > 2.6:
            continue
        segments.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        for w in (s.words or []):
            if w.word.strip():
                words.append({"start": round(w.start, 3), "end": round(w.end, 3), "word": w.word.strip(), "p": round(w.probability, 3)})
    return {"language": info.language, "language_prob": round(info.language_probability, 3), "segments": segments, "words": words}


def parse_srt(path):
    txt = Path(path).read_text(encoding="utf-8-sig")
    words, segments = [], []
    for block in re.split(r"\n\s*\n", txt.strip()):
        lines = block.strip().splitlines()
        tl = next((l for l in lines if "-->" in l), None)
        if not tl: continue
        def ts(x):
            h, m, s = x.strip().replace(",", ".").split(":"); return int(h) * 3600 + int(m) * 60 + float(s)
        a, b = [ts(x) for x in tl.split("-->")]
        text = " ".join(lines[lines.index(tl) + 1:]).strip()
        segments.append({"start": a, "end": b, "text": text})
        ws = text.split(); n = len(ws) or 1
        for i, w in enumerate(ws):  # distribute evenly (weighted by length)
            tot = sum(len(x) for x in ws) or 1; pre = sum(len(x) for x in ws[:i])
            words.append({"start": a + (b - a) * pre / tot, "end": a + (b - a) * (pre + len(w)) / tot, "word": w})
    return {"language": None, "segments": segments, "words": words}


def chunk_words(words, max_words, max_chars, max_gap=0.6, max_dur=2.5):
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or sum(len(x["word"]) + 1 for x in cur) + len(w["word"]) > max_chars
                    or w["start"] - cur[-1]["end"] > max_gap or w["end"] - cur[0]["start"] > max_dur
                    or cur[-1]["word"][-1:] in ".?!"):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur: chunks.append(cur)
    return chunks


def esc(t):
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(data, W, H, style="tiktok", platform="all", position="lower", font=None, lang=None,
              primary="#FFFFFF", highlight="#FFE600", outline="#000000", size=None, upper=None):
    lang = lang or data.get("language")
    font = font or (FONTS["vi"] if lang == "vi" else FONTS["default"])
    z = safe_zone(W, H, platform)
    vertical = H > W
    base = size or int((0.085 if style == "tiktok" else 0.058 if style in ("clean", "boxed", "karaoke") else 0.045) * (W if vertical else H * 1.2))
    upper = (style == "tiktok") if upper is None else upper
    # position -> alignment + MarginV inside safe zone
    usable_h = H - z["top"] - z["bottom"]
    if position == "lower":
        align, mv = 2, z["bottom"] + int(usable_h * 0.06)
    elif position == "middle":
        align, mv = 5, 0
    else:
        align, mv = 8, z["top"] + int(usable_h * 0.04)
    ml, mr = z["left"], z["right"]
    P, HL, O = ass_color(primary), ass_color(highlight), ass_color(outline)
    box = ass_color("#000000", 0x60)
    ol = max(2, base // 12)
    styles = [
        f"Style: Main,{font},{base},{P},{HL},{O},{box},-1,0,0,0,100,100,0,0,{3 if style == 'boxed' else 1},{ol if style != 'boxed' else max(6, base // 5)},{0 if style == 'boxed' else max(1, base // 25)},{align},{ml},{mr},{mv},1",
    ]
    ev = []
    words = data["words"]
    if not words:
        return ass_header(W, H, styles)
    cap = (lambda s: s.upper()) if upper else (lambda s: s)
    if style == "tiktok":
        chunks = chunk_words(words, 3 if vertical else 5, 16 if vertical else 32)
        for ci, ch in enumerate(chunks):
            nxt_chunk = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) else 1e9
            for i, w in enumerate(ch):
                st = w["start"]; en = ch[i + 1]["start"] if i + 1 < len(ch) else min(ch[-1]["end"] + 0.15, nxt_chunk)
                parts = []
                for j, x in enumerate(ch):
                    t = esc(cap(x["word"]))
                    if j == i:
                        parts.append(r"{\c" + HL + r"&\fscx112\fscy112\t(0,90,\fscx100\fscy100)}" + t + r"{\c" + P + r"&\fscx100\fscy100}")
                    else:
                        parts.append(t)
                pop = r"{\fad(0,0)}" if i else r"{\fscx80\fscy80\t(0,80,\fscx100\fscy100)}"
                ev.append(f"Dialogue: 0,{ass_time(st)},{ass_time(en)},Main,,0,0,0,,{pop}{' '.join(parts)}")
    elif style == "karaoke":
        for ch in chunk_words(words, 7 if vertical else 10, 28 if vertical else 48, max_dur=4):
            txt = []
            for i, w in enumerate(ch):
                nxt = ch[i + 1]["start"] if i + 1 < len(ch) else w["end"]
                txt.append(r"{\kf" + str(max(1, int(round((nxt - w["start"]) * 100)))) + "}" + esc(cap(w["word"])) + " ")
            lead = max(0, int(round((ch[0]["start"] - ch[0]["start"]) * 100)))
            # karaoke: SecondaryColour = unsung, Primary = sung -> swap so sweep goes to highlight
            ev.append(f"Dialogue: 0,{ass_time(ch[0]['start'] - 0.1)},{ass_time(ch[-1]['end'] + 0.2)},Main,,0,0,0,,"
                      r"{\1c" + HL + r"&\2c" + P + r"&\fad(80,80)}{\k" + str(10 + lead) + "}" + "".join(txt).strip())
    else:
        maxc = 32 if vertical else 42
        for ch in chunk_words(words, 14, maxc * 2, max_dur=5):
            text = " ".join(cap(w["word"]) for w in ch)
            if len(text) > maxc:  # balance into 2 lines
                ws = text.split(); best = min(range(1, len(ws)), key=lambda k: abs(len(" ".join(ws[:k])) - len(" ".join(ws[k:]))))
                text = " ".join(ws[:best]) + r"\N" + " ".join(ws[best:])
            fs = r"{\fs" + str(int(base * 0.75)) + "}" if style == "minimal" else ""
            ev.append(f"Dialogue: 0,{ass_time(ch[0]['start'])},{ass_time(ch[-1]['end'] + 0.1)},Main,,0,0,0,,{fs}{{\\fad(100,100)}}{esc(text)}")
    return ass_header(W, H, styles) + "\n".join(ev) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def style_args(p):
        p.add_argument("--style", default="tiktok", choices=["tiktok", "karaoke", "clean", "boxed", "minimal"])
        p.add_argument("--platform", default="all", choices=["tiktok", "reels", "shorts", "all"])
        p.add_argument("--position", default="lower", choices=["lower", "middle", "upper"])
        p.add_argument("--font"); p.add_argument("--size", type=int); p.add_argument("--color", default="#FFFFFF")
        p.add_argument("--highlight", default="#FFE600"); p.add_argument("--outline", default="#000000")
        p.add_argument("--upper", action=argparse.BooleanOptionalAction, default=None)
    def tr_args(p):
        p.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3 (vi: medium+ best)")
        p.add_argument("--language", default=None, help="e.g. vi, en (auto if omitted)")
        p.add_argument("--compute", default="float32", help="ctranslate2 compute type; int8 returns EMPTY output on this box's CPU, keep float32")
    t = sp.add_parser("transcribe"); t.add_argument("input"); t.add_argument("-o", "--out", required=True); tr_args(t)
    s = sp.add_parser("style"); s.add_argument("words"); s.add_argument("--video", required=True); s.add_argument("-o", "--out", required=True)
    s.add_argument("--language"); style_args(s)
    b = sp.add_parser("burn"); b.add_argument("input"); b.add_argument("ass"); b.add_argument("-o", "--out", required=True); b.add_argument("--fast", action="store_true")
    u = sp.add_parser("auto"); u.add_argument("input"); u.add_argument("-o", "--out", required=True); tr_args(u); style_args(u)
    u.add_argument("--keep", action="store_true", help="keep .words.json/.ass next to output"); u.add_argument("--fast", action="store_true")
    a = ap.parse_args()

    def do_style(data, video, out_ass):
        inf = media_info(video)
        Path(out_ass).write_text(build_ass(data, inf["width"], inf["height"], a.style, a.platform, a.position, a.font,
                                           getattr(a, "language", None), a.color, a.highlight, a.outline, a.size, a.upper), encoding="utf-8")

    if a.cmd == "transcribe":
        d = transcribe(a.input, a.model, a.language, compute=a.compute)
        Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {a.out}: lang={d['language']} words={len(d['words'])}")
    elif a.cmd == "style":
        d = parse_srt(a.words) if a.words.lower().endswith(".srt") else json.loads(Path(a.words).read_text(encoding="utf-8"))
        do_style(d, a.video, a.out); print(f"wrote {a.out}")
    elif a.cmd == "burn":
        burn_ass(a.input, a.ass, a.out, a.fast); print(f"wrote {a.out}")
    else:
        out = Path(a.out); wj = out.with_suffix(".words.json"); assf = out.with_suffix(".ass")
        d = transcribe(a.input, a.model, a.language, compute=a.compute)
        wj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        do_style(d, a.input, assf)
        burn_ass(a.input, assf, out, a.fast)
        if not a.keep:
            wj.unlink(); assf.unlink()
        print(f"wrote {out}: lang={d['language']} words={len(d['words'])}")


if __name__ == "__main__":
    main()
