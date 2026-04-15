# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Quang Đăng  
**Vai trò:** Monitoring / Docs Owner  
**Ngày nộp:** 2026-04-15  
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `monitoring/freshness_check.py`
- `docs/runbook.md`
- `docs/quality_report.md`
- `reports/group_report.md`
- Artifacts kiểm chứng: `artifacts/manifests/manifest_sprint4-redo-vi.json`, `artifacts/logs/run_sprint4-redo-vi.log`, `artifacts/eval/before_after_eval.csv`, `artifacts/eval/grading_run.jsonl`

**Kết nối với thành viên khác:**

Tôi nhận đầu ra từ các bạn Cleaning/Embed để làm phần quan sát và tài liệu hóa. Sau khi team cập nhật cleaning rule, tôi chạy lại các lệnh Sprint 3/4 để tạo bộ bằng chứng mới, rồi đồng bộ toàn bộ narrative trong quality report và group report theo đúng run_id mới. Vai trò của tôi là bảo đảm “đọc được - giải thích được - truy vết được”: mỗi claim trong báo cáo đều trỏ tới log, manifest hoặc CSV cụ thể.

**Bằng chứng (commit / comment trong code):**

Tôi dùng run `sprint3-redo-bad` và `sprint4-redo-vi` để cập nhật báo cáo. Log của run tốt có đủ: `raw_records=10`, `cleaned_records=6`, `quarantine_records=4`, `PIPELINE_OK`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định kỹ thuật chính của tôi là giữ freshness như một tín hiệu vận hành độc lập với kết quả pipeline. Cụ thể, tôi không “ép PASS freshness” chỉ để nhìn đẹp báo cáo, mà giữ nguyên SLA 24 giờ và giải thích rõ tại sao dữ liệu mẫu vẫn FAIL. Với run `sprint4-redo-vi`, `freshness_check` trả về FAIL vì `latest_exported_at=2026-04-10T08:00:00` và `age_hours` vượt SLA. Tuy nhiên pipeline vẫn `PIPELINE_OK`, tức là hạ tầng xử lý đúng nhưng nguồn dữ liệu đã stale. Tôi chọn cách trình bày này trong runbook và quality report vì nó phản ánh đúng tư duy observability: tách lỗi xử lý dữ liệu khỏi rủi ro nghiệp vụ do dữ liệu cũ.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Anomaly chính tôi xử lý là kịch bản inject khiến retrieval có thể trả thông tin hoàn tiền sai phiên bản. Triệu chứng xuất hiện ở run `sprint3-redo-bad`: expectation `refund_no_stale_14d_window` fail với `violations=1`, và file eval `after_inject_bad.csv` cho `q_refund_window` có `hits_forbidden=yes`. Tôi dùng đây làm bằng chứng Sprint 3 thay vì che lỗi, sau đó chạy run khôi phục `sprint4-redo-vi` (không có cờ inject) và kiểm lại bằng `before_after_eval.csv`. Kết quả sau fix là `hits_forbidden=no` cho cùng câu hỏi. Tôi cập nhật lại quality report theo cặp bad/good này để team có chuỗi điều tra hoàn chỉnh: symptom -> detection -> mitigation -> verification.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Before (run `sprint3-redo-bad`, file `artifacts/eval/after_inject_bad.csv`):**
- `q_refund_window`: `contains_expected=yes`, `hits_forbidden=yes`
- `top1_preview` còn cụm “14 ngày làm việc”

**After (run `sprint4-redo-vi`, file `artifacts/eval/before_after_eval.csv`):**
- `q_refund_window`: `contains_expected=yes`, `hits_forbidden=no`
- `top1_preview` chuyển sang “7 ngày làm việc”

Ngoài ra, kết quả chấm trong `artifacts/eval/grading_run.jsonl` đều đạt: `gq_d10_01`, `gq_d10_02`, `gq_d10_03` đều đúng; riêng `gq_d10_03` có `top1_doc_matches=true`.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ bổ sung kiểm tra freshness theo 2 boundary (ingest và publish) và ghi cùng lúc vào manifest để phục vụ điều kiện Distinction. Song song, tôi sẽ thêm script tổng hợp tự động `run_id -> freshness -> hits_forbidden` để việc viết report không còn thủ công mỗi lần team đổi cleaning rule.
