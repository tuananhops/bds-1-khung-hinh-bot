#!/usr/bin/env python3
"""Animated text overlays (hooks, titles, lower-thirds, CTAs) rendered via ASS, safe-zone aware.

  text_overlay.py in.mp4 -o out.mp4 --text "ĐỪNG BỎ LỠ!" --start 0 --end 2.5 --anim pop --pos top
  text_overlay.py in.mp4 -o out.mp4 --spec overlays.json
overlays.json: [{"text":"...", "start":0, "end":2, "anim":"pop|fade|slide-up|slide-left|typewriter|zoom|none",
                 "pos":"top|center|bottom|lower-third", "size":90, "color":"#FFFFFF", "accent":"#FFE600",
                 "font":"Be Vietnam Pro", "box":true, "bold":true, "sub":"optional second line"}]
Use \\N in text for manual line breaks. Fonts: Be Vietnam Pro (VN), Montserrat, Anton, Bebas Neue, Oswald, Inter...
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vtk_common import media_info, ass_header, ass_time, ass_color, safe_zone, burn_ass


def item_events(it, W, H, z, idx):
    vertical = H > W
    size = int(it.get("size") or (0.10 * W if vertical else 0.075 * H))
    font = it.get("font", "Be Vietnam Pro")
    pos = it.get("pos", "top"); anim = it.get("anim", "pop")
    st, en = float(it["start"]), float(it["end"])
    cx = z["left"] + (W - z["left"] - z["right"]) // 2
    y = {"top": z["top"] + int(size * 0.9), "center": H // 2,
         "bottom": H - z["bottom"] - int(size * 0.9),
         "lower-third": int(H * 0.72) if not vertical else H - z["bottom"] - int(size * 2.2)}[pos]
    an = 5
    x = cx
    if pos == "lower-third" and not vertical:
        an, x = 4, z["left"] + int(W * 0.02)
    c, acc, o = ass_color(it.get("color", "#FFFFFF")), ass_color(it.get("accent", "#FFE600")), ass_color("#000000")
    boxed = it.get("box", False)
    sname = f"T{idx}"
    style = (f"Style: {sname},{font},{size},{c},{acc},{o},{ass_color('#000000', 0x50) if boxed else o},{-1 if it.get('bold', True) else 0},0,0,0,100,100,0,0,"
             f"{3 if boxed else 1},{max(8, size // 6) if boxed else max(3, size // 14)},{0 if boxed else max(2, size // 22)},{an},0,0,0,1")
    dur_ms = int((en - st) * 1000)
    if anim == "pop":
        tag = rf"{{\an{an}\pos({x},{y})\fscx40\fscy40\t(0,120,\fscx115\fscy115)\t(120,200,\fscx100\fscy100)\fad(0,150)}}"
    elif anim == "zoom":
        tag = rf"{{\an{an}\pos({x},{y})\fscx100\fscy100\t(0,{dur_ms},\fscx120\fscy120)\fad(150,150)}}"
    elif anim == "slide-up":
        tag = rf"{{\an{an}\move({x},{y + int(size * 1.5)},{x},{y},0,250)\fad(200,150)}}"
    elif anim == "slide-left":
        tag = rf"{{\an{an}\move({W + size * 4},{y},{x},{y},0,300)\fad(0,150)}}"
    elif anim == "fade":
        tag = rf"{{\an{an}\pos({x},{y})\fad(300,300)}}"
    else:
        tag = rf"{{\an{an}\pos({x},{y})}}"
    text = it["text"]
    if it.get("sub"):
        text += r"\N{\fs" + str(int(size * 0.55)) + r"\b0\c" + acc + "&}" + it["sub"]
    ev = []
    if anim == "typewriter":
        chars = list(it["text"]); per = min(0.06, (en - st) * 0.6 / max(len(chars), 1))
        for k in range(1, len(chars) + 1):
            e2 = st + k * per if k < len(chars) else en
            ev.append(f"Dialogue: {idx},{ass_time(st + (k - 1) * per)},{ass_time(e2)},{sname},,0,0,0,,{{\\an{an}\\pos({x},{y})}}{''.join(chars[:k])}")
    else:
        ev.append(f"Dialogue: {idx},{ass_time(st)},{ass_time(en)},{sname},,0,0,0,,{tag}{text}")
    return style, ev


def build(items, W, H, platform):
    z = safe_zone(W, H, platform)
    styles, events = [], []
    for i, it in enumerate(items):
        s, e = item_events(it, W, H, z, i); styles.append(s); events += e
    return ass_header(W, H, styles) + "\n".join(events) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--spec"); ap.add_argument("--text"); ap.add_argument("--sub")
    ap.add_argument("--start", type=float, default=0); ap.add_argument("--end", type=float, default=3)
    ap.add_argument("--anim", default="pop"); ap.add_argument("--pos", default="top")
    ap.add_argument("--size", type=int); ap.add_argument("--font", default="Be Vietnam Pro")
    ap.add_argument("--color", default="#FFFFFF"); ap.add_argument("--accent", default="#FFE600")
    ap.add_argument("--box", action="store_true"); ap.add_argument("--platform", default="all")
    ap.add_argument("--save-ass"); ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    items = json.loads(Path(a.spec).read_text(encoding="utf-8")) if a.spec else [
        {"text": a.text, "sub": a.sub, "start": a.start, "end": a.end, "anim": a.anim, "pos": a.pos, "size": a.size,
         "font": a.font, "color": a.color, "accent": a.accent, "box": a.box}]
    inf = media_info(a.input)
    ass = Path(a.save_ass or Path(a.out).with_suffix(".overlay.ass"))
    ass.write_text(build(items, inf["width"], inf["height"], a.platform), encoding="utf-8")
    burn_ass(a.input, ass, a.out, a.fast)
    if not a.save_ass: ass.unlink()
    print(f"wrote {a.out} ({len(items)} overlays)")


if __name__ == "__main__":
    main()
