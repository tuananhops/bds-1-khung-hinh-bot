# Video Toolkit — for Editor 05 & Editor 06

Pro short-form editing toolkit in `vendor/video-toolkit` (wrapper `./vtk`; set `VTK_PY` to your venv python).
**Default output is 1080×1920 9:16** for TikTok / Instagram Reels / YouTube Shorts.

Run any tool as `vtk <tool> ...` (wrapper `vendor/video-toolkit/vtk`; `fonts/`, `luts/`, `sfx/`, `venv/` không kèm trong repo: cài font theo rules.md, sfx tạo bằng `vtk audio gen-sfx`), or
`venv/bin/python scripts/<tool>.py ...`. Every tool supports `-h`.
Set `VTK_FAST=1` for quick preview encodes (veryfast); omit for final quality (x264 slow, CRF 18).

## Installed
| Component | Version / notes |
|---|---|
| FFmpeg | 7.1.5 (Debian): libx264, libx265, libass, freetype/fribidi/harfbuzz, lut3d, xfade, loudnorm, sidechaincompress, minterpolate, rubberband, vidstab |
| ImageMagick | 7.1.1 (`magick`, `convert`, `montage`) |
| Python venv | `venv/` (Python 3.13): moviepy 2.2.1, opencv-python-headless 5.0, scenedetect 0.7.1, librosa 1.0, faster-whisper 1.2.1 (+ctranslate2 4.8.2), numpy, pillow, pydub, colour-science 0.4.7, av 15.1 |
| Fonts | `fonts/` (also installed system-wide): **Be Vietnam Pro** (Regular/Bold/ExtraBold/Black), **Montserrat** (Regular/SemiBold/Bold/ExtraBold/Black, static), Anton, Bebas Neue, Oswald, Inter, Lexend, Playfair Display (+ Noto Sans, DejaVu, Roboto system) |
| LUTs | `luts/`: teal_orange, cinematic, warm, bw, moody, vibrant, identity (33³ .cube) |
| SFX | `sfx/`: whoosh, hit, riser, glitch, pop (synthesized; regenerate with `vtk audio gen-sfx`) |
| Face model | `models/face_detection_yunet_2023mar.onnx` (OpenCV YuNet, for reframe tracking) |
| Whisper models | cached in `~/.cache/huggingface` (tiny, base, small). medium / large-v3 download on first use |
| Extras | espeak-ng (TTS for tests) |

## Recommended workflow: match a reference video
```bash
# 1. Study the reference: pacing, BPM, beat-sync, look, loudness + one frame per shot
vtk analyze ref.mp4 -o brief.json --contact-sheet ref_sheet.jpg
#    -> read brief.json "recommendations" (e.g. "use beat_cut.py --every 2", warm/teal, high contrast)
# 2. Reframe 16:9 raw footage to 9:16 with face/subject tracking
vtk reframe raw_16x9.mp4 -o raw_v.mp4                    # --mode auto|face|motion|center|blur
# 3. Cut b-roll to the beat with the reference's rhythm
vtk beatcut --music song.mp3 --clips broll/ --every 2 --punch 4 --flash 8 --mode energy -o montage.mp4
# 4. Speed ramps on hero moments
vtk ramp montage.mp4 --hero 3.0 -o montage_ramp.mp4
# 5. Join sections with transitions
vtk transitions join intro.mp4 montage_ramp.mp4 talk.mp4 -t whip,flash,glitch -d 0.3 -o cut.mp4
# 6. Match the reference look, then add a creative LUT
vtk grade match cut.mp4 --ref ref.mp4 --strength 0.8 --then-lut teal_orange -o graded.mp4
# 7. Hook text + animated captions (Vietnamese OK)
vtk text graded.mp4 --text "ĐỪNG BỎ LỠ!" --sub "Bí quyết..." --start 0 --end 2.5 --anim pop --pos top --box -o hook.mp4
vtk subs auto hook.mp4 --language vi --style tiktok --model medium -o captioned.mp4
# 8. Music bed ducked under voice, SFX on transitions, -14 LUFS
vtk audio mix captioned.mp4 --music song.mp3 --duck --music-db -8 -o mixed.mp4
vtk audio sfx mixed.mp4 --at 7.5:whoosh,12:hit -o sfx.mp4
# 9. Deliver
vtk render sfx.mp4 --all-platforms -o deliver/            # tiktok / reels / shorts
```
A complete runnable version is `test/run_e2e.sh`.

## Tools
### analyze_reference.py (`vtk analyze`)
Scene cuts (PySceneDetect ContentDetector, `--threshold`), shot list, avg/median shot length, cuts/min,
tempo + beat grid + onsets + energy curve (librosa), % of cuts on beats, integrated LUFS / true peak,
brightness / contrast / saturation / warmth / tint, Lab mean/std, motion energy, aspect;
plain-language `recommendations`; `--contact-sheet` makes a JPG grid (one frame per shot).

### beat_cut.py (`vtk beatcut`)
`--every N` beats or `--pattern 4,2,2,1,1`; `--mode sequential|random|energy` (energy = most motion);
`--punch K` zoom punch every K shots; `--flash K` white flash every K cuts; `--start/--duration` (music window);
`--preset` (default 1080p-9x16), `--fit cover|fit|blur`; `--edl cuts.json`. Frame-accurate, no drift.

### transitions.py (`vtk transitions`)
`join`: crossfade, dissolve, dip, flash, zoom, punch, whip/whip-right/whip-up (slide + directional motion blur),
glitch (pixelize + RGB split + noise), blur, wipe, circle, slide-up, smooth, squeeze, or any raw xfade name.
`-t` list cycles; audio is crossfaded; clips without audio get silence. Default output 1080×1920.
`fx`: `--punch --flash --glitch --whip --shake` at comma-separated times on one clip.

### color_grade.py (`vtk grade`)
`apply --lut NAME|file.cube [--intensity 0.6]`, `match --ref video|image [--strength] [--save-lut] [--then-lut]`
(Reinhard Lab transfer baked into a 33³ LUT), `finish` (contrast/saturation/gamma, `--vignette --sharpen --grain N`),
`gen-luts` (rebuild built-in LUTs). Any third-party .cube LUT works.

### speed_ramp.py (`vtk ramp`)
`--keys "t:speed,..."` (smooth interpolated curve), `--hero T` (fast→slow-mo→fast), `--constant 0.5`.
`--interp blend|mci|none` (mci = optical-flow slow-mo: best quality, ~3 min per 5 s of 1080p),
`--audio keep|mute` (keep = pitch-preserved atempo).

### reframe.py (`vtk reframe`)
16:9 → 9:16 (or `--size 1080x1080` etc.). `--mode auto` = YuNet faces → motion centroid → centre; smooth
virtual camera (`--smooth`, `--max-speed`, `--deadzone`), hard re-centre on scene cuts; `--mode blur` = fit on blurred background.

### subtitles.py (`vtk subs`)
`transcribe` (faster-whisper word timestamps, VAD, hallucination filter) → `style` (ASS) → `burn`; or `auto` for all.
Styles: **tiktok** (2-3 word chunks, active word highlighted + pop), **karaoke** (colour sweep), **clean**, **boxed**, **minimal**.
`--platform tiktok|reels|shorts|all` safe-zone margins, `--position lower|middle|upper`, `--font --size --color --highlight --upper/--no-upper`.
Vietnamese: `--language vi` → Be Vietnam Pro automatically; use `--model medium` or `large-v3` for best VI accuracy.
`style` also accepts an existing `.srt` (edit the words JSON or SRT to fix typos before burning).

### text_overlay.py (`vtk text`)
Hooks / titles / lower-thirds / CTAs; anims pop, zoom, slide-up, slide-left, fade, typewriter;
positions top, center, bottom, lower-third (inside safe zone); `--box`; multiple items via `--spec overlays.json`.

### audio.py (`vtk audio`)
`loudnorm` (2-pass, -14 LUFS, -1 dBTP), `measure`, `mix --music --duck` (sidechain ducking under voice + loudnorm),
`sfx --at t:name,...`, `gen-sfx`, `denoise` (highpass + FFT denoise + compressor).

### render.py (`vtk render`)
Presets (`--list`): **vertical (default, 1080×1920)**, tiktok, reels, shorts, 4k-vertical, youtube (1920×1080), 4k-16x9, square, portrait-4x5.
`--fps 30|60`, `--all-platforms`, `--reframe smart|center|blur|fit` when aspect differs.
Encode: H.264 High, CRF 18, yuv420p, BT.709 tags, 2 s GOP, maxrate cap, `+faststart`, AAC 320k 48 kHz, 2-pass loudnorm -14 LUFS.

## Safe zones (1080×1920, px kept clear)
| platform | top | bottom | left | right |
|---|---|---|---|---|
| tiktok | 160 | 480 | 60 | 150 |
| reels | 220 | 420 | 60 | 130 |
| shorts | 180 | 400 | 60 | 150 |
| all (default) | 220 | 480 | 60 | 150 |
Defined in `scripts/vtk_common.py` (`SAFE_ZONES_9x16`).

## Tests
`test/make_test_media.sh` (synthetic clips, 120 BPM music, Vietnamese TTS, beat-cut reference) and
`test/run_e2e.sh` (full pipeline, ~2.5 min with VTK_FAST=1). Outputs in `test/e2e/`, QA renders in `test/out/`.

## Known limitations
- faster-whisper **int8 returns empty transcripts on this CPU** (ctranslate2 4.8.2); default is `--compute float32` (slower, correct).
- PyAV pinned `<16` (faster-whisper 1.2.1 breaks with av 16); subtitles also decode audio through system ffmpeg.
- `--interp mci` and `--reframe blur`/`--fit blur` are CPU-heavy; preview with `VTK_FAST=1`.
- No GPU; all encoding is CPU (8 cores).
- `scenedetect` pulls in `opencv-python` alongside `opencv-python-headless` (same version, works).

## Added 2026-10-12 (Editor Academy extension)
key (chroma), stab (vidstab), clean (arnndn/afftdn dialogue chain; model models/rnnoise/sh.rnnn), silencecut, scopes, mapfx (3D ground text + red sweep),
leak (light leaks/grain/vignette), logo (logo reveal), broll (auto B-roll), qc (auto QC). Docs: see repo rules.md
