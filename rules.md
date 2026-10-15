# rules.md: Quy tắc làm việc (bắt buộc)

## 1. Layout & thông số giao
- **Chỉ 1 khung EDITED full 1080x1920**: không ô RAW, không nền mờ, không bo góc, không nhãn EDITED/RAW. Chữ ASS burn thẳng lên bản edit.
- H.264 yuv420p 30fps CFR, AAC 48k 256k, +faststart, bt709. **-14 LUFS (±1.5), TP ≤ -1 dBTP.**
- **File < 95MB** (giới hạn upload 100MB). Bitrate `vb = min(7000, 92*8*1000/dur - 300)` kbps. KHÔNG dùng CRF (crf 21 từng ra file quá nặng).
- **`vtk qc <file> --platform all --json qc.json` phải PASS** (PASS with warnings được, nhưng đọc hết warning) trước khi giao. FAIL thì không giao.
- Vùng an toàn: chữ quan trọng x120–888, y288–1248. Phụ đề y1000–1250 (hoặc dưới cằm nếu né mặt). Không đặt chữ ở x>900 (icon TikTok) hay y<250 (tab). Không mở bằng khung đen, logo hay fade (qc FAIL).

## 2. Sở thích đã duyệt của chủ
- **Không bộ lọc màu/grade/LUT** (bản LUT teal-orange từng bị chê). Giữ màu tự nhiên, chỉ **cứu vùng chói**: soft-knee nén luma >0.72 về 0.88, tăng chroma +25% vùng sáng (`highlight_fix.py`).
- **Luôn giảm ồn giọng**: `vtk clean --denoise rnn` + `afftdn=nr=12:nf=-40,highpass=f=80`. Đừng khử quá tay (giọng sẽ thành robot).
- **Nhạc**: deep house sáng ~122BPM, nghe rõ trên loa điện thoại (kick có click), duck sidechain dưới giọng (loudnorm -26 → sidechaincompress). Không để đoạn nào im lặng. Ads nên dùng nhạc tự tổng hợp (`make_music.py`) hoặc thư viện thương mại được phép.
- **Màn tiêu đề 3s đầu** (theo reel FB anh gửi): chữ giá to phóng vào rồi đáp thành **huy hiệu nổ đỏ/vàng** nghiêng, **tiêu đề đỏ/trắng viền đậm gõ từng chữ phía trên đầu** người dẫn, dòng 2 `73m² x 4 PN`. Kéo dài ~3.2s, frame đầu đã có chữ.
- **SFX mở đầu thật TO**: whoosh lao vào, rồi **TING + BOOM** lúc huy hiệu đáp (~0.25s). To hơn giọng (~+7 dB so với giọng), nhạc hạ trong giây đầu. (Đã duyệt.)
- **Sau intro CHỈ dùng 3 tiếng**: **ting** (chữ từ khóa/CTA hiện), **cash** (chữ giá/tiền TỶ, TRIỆU), **whoosh** (cắt b-roll vào/ra, đỉnh whoosh trùng frame cắt).
  - Khớp frame (lệch ≤20 ms, kiểm bằng `verify_sync.py`), cách nhau ≥0.4s, ưu tiên cash > ting > whoosh.
  - Mức thấp hơn đỉnh giọng 3–5 dB (cash -3, ting -4, whoosh -5).
  - **Không pop từng cụm, không riser/hit** (bản 3 bị chê vì SFX chậm và đục).
- **Chữ không bao giờ che mặt**: dò mặt YuNet (`facemap.py`), đặt chữ dưới cằm hoặc trên đầu, co size; nếu không còn chỗ thì drop.
- **Chữ nghệ thuật vàng kim (style v7)**:
  - Cụm 1–4 từ đồng bộ lời nói, Paytone One trắng, bóng đen mềm.
  - Từ khóa/số: Bungee IN HOA, gradient 3 lớp #FFE08A→#D4A017→#B8860B, viền #8B6508.
  - Từ cảm xúc: Pacifico vàng kim + "!".
  - Giá cũ có gạch ngang vàng. CTA là banner trắng bo góc trượt lên, chữ Paytone One 96 vàng kim.
  - Pop 70→110→96→100% trong 230ms.
  - **Bungee thiếu dấu tiếng Việt (À, Ằ, Ẫ…)**: tiêu đề/từ khóa có dấu dùng **Paytone One** (`kw_font`).
- **Không dùng chữ đỏ phẳng hay font thường** cho phụ đề thân video (đã bị chê). Màu đỏ chỉ dùng trong màn intro.
- **B-roll**: ưu tiên footage hoặc ảnh chủ gửi. Lấy từ web thì chỉ dùng VIDEO (YouTube qua yt-dlp), **không dùng ảnh tĩnh từ web** (đã bị chê).
- **CTA**: chỉ dùng tên người dẫn nếu họ tự nói tên trong video ("Alo [tên] xem nhà ->"). Một hành động duy nhất, giữ ≥2.5s.
- **Đặt tên file giao**: tiếng Việt dễ đọc, có số bản, vd `Nhà Văn Cao - 7948 - bot 1 khung hình - bản 4.mp4`. Mỗi lần sửa thì tăng số bản.
- Up vào **thư mục Drive của chủ (hỏi chủ)**. Up xong video nào thì gửi link video đó ngay.

## 3. Quảng cáo BĐS: nội dung & tuân thủ
- Hook ≤3s: cảnh "wow" + chữ có số cụ thể (giá/vị trí/câu hỏi). Không mở bằng "Xin chào mọi người" hay mặt tiền chậm.
- Cấu trúc: Hook → bối cảnh/vị trí → tour 4–6 điểm (1.5–3s/cảnh) → reveal → GIÁ + pháp lý (chữ to nhất, ≥2s) → CTA.
- Có phụ đề suốt video (~80% người xem tắt tiếng). Mỗi lúc chỉ 1 thông điệp chính.
- Bản dài hơn 60s thì đề xuất thêm bản 30–60s và biến thể 9–15s.
- **Luật KD BĐS 2023 Đ8**: không lừa dối, **không hứa lợi nhuận** ("lãi x%/năm", "x2 sau 1 năm"), không "rẻ nhất/duy nhất/số 1" nếu không chứng minh được.
- **Bỏ câu nói sai sự thật** và báo chủ. Vd người dẫn nói "bớt luôn 10%" nhưng 4,28→3,98 tỷ chỉ ~7%, nên bỏ câu đó.
- Ghi pháp lý (sổ hồng…) chỉ khi chủ xác nhận. Phối cảnh/ảnh minh họa phải ghi "Hình ảnh minh họa". Che CCCD/biển số lọt khung.

## 4. Cài đặt bắt buộc
- **ffmpeg** ≥6 có libx264, libass, loudnorm, sidechaincompress, arnndn, afftdn, vidstab.
- **Python venv** + `scripts/requirements.txt` (numpy, scipy, soundfile, opencv-python-headless, faster-whisper, yt-dlp…).
- **faster-whisper dùng `compute_type="float32"`**, KHÔNG int8 (int8 ra transcript rỗng trên CPU). Model `medium`, `language="vi"`.
- **yt-dlp bản nightly** (`pip install -U --pre yt-dlp`) + **Node.js** làm JS runtime. YouTube: `--js-runtimes node --extractor-args youtube:player_client=tv_embedded`.
- **Font** (cài system-wide, `fc-cache -f`): **Paytone One, Bungee, Pacifico, Be Vietnam Pro** (Google Fonts). Kiểm: `fc-list | grep -iE "paytone|bungee|pacifico|vietnam"`.
- **vtk toolkit**: `vendor/video-toolkit` (wrapper `vtk`, cần venv riêng hoặc `VTK_PY`). Model YuNet + rnnoise có sẵn trong `models/`.

## 5. Lỗi đã mắc & bài học
| Lỗi | Bài học |
|---|---|
| faster-whisper int8 trả transcript rỗng | Luôn dùng float32 |
| venv của vtk tự biến mất (lệnh vtk lỗi python) | Dựng lại venv: `python3 -m venv venv && venv/bin/pip install -r scripts/requirements.txt`, rồi chạy `vtk qc -h` để kiểm |
| Bungee không có glyph À/Ằ (ô vuông) | Tiêu đề/chữ có dấu dùng Paytone One. Luôn xem frame preview chữ |
| Bản 2: SFX intro quá nhỏ, chủ không nghe thấy | Opener phải to hơn giọng: stem riêng peak -1 dBFS, nhạc hạ giây đầu |
| Bản 3: SFX phía sau bị trễ và đục (pop, riser, hit lẫn lộn) | Chỉ ting/cash/whoosh, transient ở sample 0, whoosh đặt sớm 0.25s, làm tròn lên frame, đo bằng verify_sync |
| Bản 4: lỡ bỏ tiếng pop 1.5s ở intro khi dọn SFX | Khi dọn SFX phải giữ nguyên stem intro đã duyệt và báo chủ mọi thay đổi |
| CRF 21 ra file >95MB | Dùng công thức bitrate theo thời lượng |
| B-roll ảnh tĩnh từ web bị chê | Chỉ video (footage chủ hoặc YouTube) |
| LUT/grade màu bị chê | Không grade, chỉ cứu chói |
| Whisper sai chính tả VI (ngổ→ngủ, lươi→nơi, "4 ,2 tỷ") | Bảng `fix` + `merge` trong config gold_text, rà lại toàn bộ chữ |
| File ngắn: loudnorm 1 pass ra -16.5 LUFS, TP vượt sau AAC | mix_audio pass 2 đo rồi bù gain + limiter 0.66 chừa headroom cho AAC |
| Shell treo khi gọi lệnh mạng | Bọc `timeout 20 …` hoặc chạy nền, poll output |

## 6. Ghi chú giao diện công cụ
- **vtk**: `vtk <tool> -h` trước khi dùng. Hay dùng: `analyze`, `reframe --mode face|motion`, `stab --smoothing 15`, `clean --denoise rnn`, `subs transcribe --language vi --model medium`, `silencecut`, `qc --platform all --json`. `VTK_FAST=1` chỉ để nháp. Warning "bitrate 7.4 Mbps (target 10-20)" chấp nhận được (do giới hạn 95MB).
- **yt-dlp tải reel Facebook**: `yt-dlp "https://www.facebook.com/reel/<id>" -o ref.mp4` chạy được **không cần cookies**. Phân tích 3s đầu: `ffmpeg -ss 0 -t 3 -i ref.mp4 -vf fps=10,scale=270:-1,tile=6x5 sheet.png`, kèm `vtk analyze`.
- **Google Drive**: up bằng công cụ upload của connector Drive (file đến 100MB) vào thư mục của chủ, đặt `name` là tên tiếng Việt. Gửi link dạng xem trực tiếp. Không đổi quyền chia sẻ nếu chủ chưa bảo.
- **ASS/libass**: font gọi bằng `\fn<Tên>` phải cài system-wide. Toạ độ theo PlayRes 1080x1920. Màu ASS là `&HBBGGRR&`.
