---
name: Master rough cut talking-head
description: >-
  Dùng khi cần cắt thô (rough cut) video talking-head thô: bỏ nói vấp, câu hỏng,
  lặp từ, khoảng lặng; giữ take sạch nhất; chuẩn 9:16 và -14 LUFS; xử lý hàng
  loạt nhiều video.
---
# Mục tiêu
Từ video thô talking-head, xuất bản cắt thô sạch: chỉ giữ take tốt nhất của mỗi câu, cắt đúng chỗ ngắt nghỉ tự nhiên, không còn từ lặp, từ bị cụt, false start, ậm ừ. Âm lượng -14 LUFS, khung 9:16. Nhanh nhưng không hy sinh chất lượng.

# Công cụ
- ffmpeg/ffprobe; whisper (faster-whisper hoặc whisperx) với word_timestamps=True, ngôn ngữ đúng (vd vi).
- Python để dựng danh sách đoạn giữ (EDL).

# Quy trình
1. **Kiểm tra nguồn**: `ffprobe` lấy độ dài, fps, độ phân giải, sample rate, rotation. Ghi lại fps để snap cắt theo frame.
2. **Tách audio**: `ffmpeg -i in.mp4 -vn -ac 1 -ar 16000 a.wav`.
3. **Phiên âm mức từ**: whisper word-level timestamps + VAD. Lưu JSON (word, start, end, prob). Nếu có whisperx thì align để timestamp chính xác hơn.
4. **Bản đồ khoảng lặng**: `ffmpeg -i a.wav -af silencedetect=noise=-35dB:d=0.25 -f null -` → danh sách silence. Điều chỉnh ngưỡng theo noise floor thực tế (đo bằng astats).
5. **Chia câu/ý**: gom từ thành segment theo dấu câu và khoảng lặng ≥0.35s.
6. **Phát hiện take hỏng** (đánh dấu loại bỏ):
   - False start: segment bị bỏ dở rồi nói lại câu có cùng 2–5 từ đầu (so sánh n-gram/độ tương đồng chuỗi ≥0.6) → giữ lần nói SAU CÙNG hoàn chỉnh, trừ khi lần trước sạch hơn.
   - Lặp từ liền kề ("tôi tôi", "và và"), từ cụt (độ dài từ <0.12s kèm prob thấp, hoặc từ chưa trọn).
   - Ậm ừ/filler: ờ, ừm, à, uh, um, kiểu như (chỉ khi đứng riêng/thừa).
   - Câu nói lại sau lời tự sửa ("không, nói lại", "cắt", "lại nhé").
   - Từ prob thấp bất thường → nghe kiểm tra lại đoạn đó.
   - Khi có nhiều take của cùng một câu: chấm điểm theo trọn vẹn, không vấp, prob trung bình, nhịp đều; chọn take cao nhất.
7. **Đặt điểm cắt**:
   - Cắt TRONG khoảng lặng, không bao giờ giữa từ. Điểm vào = start từ đầu − 0.08–0.12s; điểm ra = end từ cuối + 0.12–0.2s (giữ hơi thở cuối tự nhiên).
   - Snap tới khung hình gần nhất trong vùng lặng.
   - Rút khoảng lặng dài còn ~0.25–0.4s, không xóa sạch để giữ nhịp tự nhiên.
   - Kiểm tra mức năng lượng tại mỗi điểm cắt (RMS 20ms) phải thấp; nếu không, dời tới điểm thấp nhất lân cận.
8. **Render**:
   - Dùng filter `trim/atrim` + `concat` (hoặc xuất từng đoạn rồi concat) với re-encode để cắt chính xác frame.
   - Crossfade audio 10–20ms tại mỗi nối (`acrossfade` hoặc afade ngắn) chống tiếng click.
   - Khung 9:16: nếu nguồn ngang thì crop giữa theo mặt người (ưu tiên giữ mặt ở 1/3 trên); nguồn dọc giữ nguyên 1080x1920.
   - Video: libx264 -crf 18 -preset medium, giữ fps gốc; audio aac 192k 48kHz.
9. **Chuẩn âm lượng -14 LUFS** hai pass: pass 1 `loudnorm=I=-14:TP=-1:LRA=11:print_format=json`, pass 2 dùng measured_* với linear=true.
10. **QA bắt buộc** trước khi giao:
    - Phiên âm lại file đã cắt; dò lại từ lặp liền kề, false start, filler còn sót → sửa và render lại.
    - Nghe nhanh mọi điểm nối (±0.5s) tìm click, cụt chữ, hụt hơi.
    - Đo lại LUFS (ebur128) trong khoảng -14 ±0.5, true peak ≤ -1 dBTP.
    - Kiểm tra A/V sync và độ phân giải 1080x1920.
11. **Giao**: đặt tên `<tên gốc>_roughcut.mp4`, kèm EDL (danh sách đoạn giữ) và ghi chú ngắn: độ dài trước/sau, số chỗ đã bỏ, đoạn nào cần editor để ý.

# Chạy hàng loạt
- Xử lý liên tục toàn bộ video, không dừng hỏi giữa chừng; xong video nào giao ngay video đó để khâu hậu kỳ làm song song.
- Nếu có cảnh báo dùng tài khoản ≥80%: dừng mọi việc và báo chủ.
