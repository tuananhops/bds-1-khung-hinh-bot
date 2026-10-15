# scripts/: công cụ dòng lệnh

## Cài đặt
```bash
sudo apt install -y ffmpeg nodejs fontconfig
python3 -m venv venv && . venv/bin/activate
pip install -r scripts/requirements.txt && pip install -U --pre yt-dlp
# Font: tải Paytone One, Bungee, Pacifico, Be Vietnam Pro từ Google Fonts vào ~/.local/share/fonts rồi:
fc-cache -f && fc-list | grep -iE "paytone|bungee|pacifico|vietnam"
# Toolkit vtk:
export PATH=$PWD/vendor/video-toolkit:$PATH VTK_PY=$PWD/venv/bin/python
vtk qc -h
```

## Công cụ (đều có `--help`)
| Script | Việc |
|---|---|
| `roughcut.py raw.MOV --words w.json -o rc.mov [--drop a-b,..]` | Cắt thô theo transcript (skill master-rough-cut) |
| `highlight_fix.py in out` | Cứu vùng chói (không grade) |
| `facemap.py video faces.json` | Bản đồ mặt YuNet 5fps |
| `title_intro.py -o intro.ass --sfx intro.txt --line1 .. --line2 .. --badge .. --red ..` | Intro 3s + stem SFX mở đầu to (`intro.wav`) |
| `gold_text.py --words --faces --config -o fx7.ass` | Chữ vàng kim v7, né mặt, CTA |
| `sfx_cues.py --ass fx7.ass --plan plan.json --voice voice.wav --cta T -o sfx.wav` | SFX ting/cash/whoosh khớp frame |
| `verify_sync.py sfx.wav\|final.mp4 --events sfx_events.json --sfx-dir sfx` | Đo lệch SFX (≤20ms → PASS) |
| `make_music.py -o music.wav --dur N` | Nhạc deep house 122BPM tự tổng hợp |
| `mix_audio.py --voice --music [--sfx] [--intro] -o mix.wav` | Mix giọng/nhạc duck/SFX, 2 pass về -14 LUFS |
| `render_final.py --video --audio --ass .. --ass .. -o "Tên.mp4" --qc` | Render 1 khung <95MB + cover + vtk qc |

## Pipeline mẫu
```bash
vtk subs transcribe raw.MOV --language vi --model medium -o w_raw.json
python scripts/roughcut.py raw.MOV --words w_raw.json -o rc.mov --drop "23.8-25.5"
vtk subs transcribe rc.mov --language vi --model medium -o words.json     # words trên bản đã cắt
python scripts/highlight_fix.py edit_v.mp4 edit_hl.mp4                    # edit_v = rc + b-roll theo plan.json
python scripts/facemap.py edit_hl.mp4 faces.json
python scripts/title_intro.py -o intro.ass --sfx intro.txt --line1 "NHÀ ĐẸP VĂN CAO" --line2 "73m² x 4 PN" --badge "3,98 TỶ" --red "NHÀ ĐẸP"
python scripts/gold_text.py --words words.json --faces faces.json --config text_cfg.json -o fx7.ass
ffmpeg -i rc.mov -vn -ac 1 -ar 48000 rc48.wav && vtk clean rc48.wav -o vc1.wav --denoise rnn
python scripts/sfx_cues.py --ass fx7.ass --plan plan.json --voice vc1.wav --cta 124 -o sfx.wav --events sfx_events.json
python scripts/make_music.py -o music.wav --dur 130
python scripts/mix_audio.py --voice vc1.wav --denoise --music music.wav --sfx sfx.wav --intro intro.wav -o mix.wav
python scripts/render_final.py --video edit_hl.mp4 --audio mix.wav --ass fx7.ass --ass intro.ass -o "Nhà X - bản 1.mp4" --qc
python scripts/verify_sync.py "Nhà X - bản 1.mp4" --events sfx_events.json --sfx-dir sfx
```
Ghép b-roll (edit_v.mp4) đang làm theo `plan.json` (BR = [start,end,v|i,nguồn]) bằng `vtk broll` hoặc `vtk beatcut`. Xem `rules.md`.

## Smoke test đã chạy (15/10/2026)
- Tất cả `--help` OK.
- Dữ liệu thật Văn Cao 7948: `gold_text` cho 138 cụm, 30 từ khóa, 0 drop; `sfx_cues` cho whoosh 35, ting 24, cash 6 (khớp bản 4); `verify_sync` lệch 0.0ms, PASS.
- Clip 8s: `roughcut`, rồi `highlight_fix` (pixel >235 giảm 13.1%→0%), `facemap` (40/40), `make_music`, `mix_audio`. Cuối cùng `render_final --qc` ra 7.4MB, **QC PASS with warnings** (-15.1 LUFS, TP -1.5).
