# Bot edit BĐS 1 khung hình

Gói "đóng gói bộ não" cho một bot AI làm **video quảng cáo bất động sản dọc 9:16** (TikTok, Reels, Shorts).
- Bot chỉ dựng **1 khung EDITED full 1080x1920**. Mở đầu bằng màn tiêu đề 3s có SFX to, chữ vàng kim né mặt, SFX ting/cash/whoosh khớp frame.
- Không grade màu. Giảm ồn giọng. Bản giao phải PASS `vtk qc` và nhỏ hơn 95MB.

## Giao cho bot mới
```bash
git clone https://github.com/tuananhops/bds-1-khung-hinh-bot.git
```
Rồi bảo bot: **"Đọc AGENTS.md rồi làm theo."** (Claude Code tự đọc `CLAUDE.md`, nội dung giống hệt.)
Bot sẽ đọc `skills/`, rồi `rules.md`, rồi `scripts/README.md` để cài đặt, và xem `examples/` làm mẫu.

## Cấu trúc
```
AGENTS.md / CLAUDE.md     hướng dẫn cho bot (danh tính, giọng điệu, quy trình + điểm DỪNG)
rules.md                  quy tắc, sở thích đã duyệt, cài đặt, lỗi & bài học, ghi chú công cụ
skills/                   skill dùng nguyên văn (master-rough-cut-talking-head)
scripts/                  công cụ CLI (intro, chữ vàng kim, SFX, mix, render+QC...) + requirements.txt
examples/                 ví dụ đã duyệt (Văn Cao 7948 bản 4: config, plan, cue SFX)
vendor/video-toolkit/     toolkit `vtk` (analyze, reframe, clean, subs, qc...)
```
Không chứa video/âm thanh, token hay thông tin cá nhân. Thư mục giao file do chủ cung cấp lúc làm việc.
