# Ví dụ đã duyệt: Nhà Văn Cao, clip 7948, bản 4
Video 2:07, 81MB, QC PASS. Chủ duyệt: tiêu đề intro, SFX mở đầu to, bộ ting/cash/whoosh khớp frame.

## Kịch bản (dàn ý sau cắt thô)
1. 0–3.2s **Intro**: huy hiệu "3,98 TỶ" nổ phóng vào, "NHÀ ĐẸP VĂN CAO" (NHÀ ĐẸP đỏ) gõ từng chữ trên đầu, dòng "73m² x 4 PN".
2. Mở lời: giảm giá, 73m², ô tô đỗ cửa, ngõ 3m. B-roll ngõ và mặt tiền.
3. Giá: "4,28 tỷ" gạch ngang, rồi "3,98 tỷ" (cash). **Bỏ câu "bớt luôn 10%"** vì thực tế chỉ ~7%.
4. Tour: phòng khách, bếp, 4 phòng ngủ khép kín, WC, sân trước sân sau, khe thoáng hướng Đông Nam. B-roll khớp lời.
5. Công năng: kinh doanh, ô tô tải, chỗ để 4 xe.
6. 124s **CTA** banner "Alo [TÊN] xem nhà ->" (tên người dẫn tự nói trong video).

## File
- `text_cfg.json`: cấu hình `gold_text.py` (fix chính tả, ghép giá, từ khóa, emo, gạch giá, CTA).
- `plan.json`: các đoạn b-roll (BR) trên timeline đã cắt, dùng cho whoosh.
- `sfx_events.json`: 65 cue đã duyệt [thời điểm, loại, chữ].
- Lệnh intro:
  `python scripts/title_intro.py -o intro.ass --sfx intro.txt --line1 "NHÀ ĐẸP VĂN CAO" --line2 "73m² x 4 PN" --badge "3,98 TỶ" --red "NHÀ ĐẸP"`
- Đoạn bỏ khi cắt thô (giây trên file gốc): 23.8–25.5, 27.6–32.9, 66.03–67.3, 83.0–87.9, 94.15–94.92, 125.45–125.94, 134.3–139.3, 147.68–149.7.
- Tên file giao: `Nhà Văn Cao - 7948 - bot 1 khung hình - bản 4.mp4`.
