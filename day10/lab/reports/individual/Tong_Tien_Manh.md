# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Tống Tiến Mạnh  
**Vai trò:** Cleaning  
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `transform/cleaning_rules.py` — toàn bộ phần mở rộng 3 rule mới (Rule 4, 5, 6)

Tôi phụ trách module `transform/cleaning_rules.py`, cụ thể là thiết kế và triển khai 3 cleaning rule mới ngoài baseline: `fix_leave_10_to_12` (sửa ngày phép năm sai 10 → 12 trong `hr_leave_policy`), `fix_sick_leave_stale` (sửa ngày nghỉ ốm sai 5/7 → 10), và `fix_lockout_threshold_stale` (sửa ngưỡng khóa tài khoản sai 3/10 → 5 lần trong `it_helpdesk_faq`). Tôi đọc các file nguồn trong `data/docs/` để xác định giá trị chuẩn, viết regex tương ứng và tích hợp vào hàm `clean_rows()` với trường `metric_impact` cho từng rule.

**Kết nối với thành viên khác:**

Rule của tôi feed trực tiếp vào bước embed (Embed Owner) — chunk sau khi được sửa sẽ có `chunk_id` ổn định nhờ `_stable_chunk_id()`, đảm bảo upsert idempotent vào Chroma.

**Bằng chứng (commit / comment trong code):**

Comment `# --- RULE MỚI (sinh viên thêm) ---` và `# Rule 4/5/6` trong `cleaning_rules.py`; docstring từng helper function ghi rõ nguồn chuẩn (file `.txt` và mục tương ứng).

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi chọn thiết kế cả 3 rule mới theo kiểu **fix rule** (sửa text, giữ row trong cleaned) thay vì quarantine, vì mục tiêu là đưa thông tin đúng vào vector store để retrieval trả về kết quả chính xác — nếu quarantine thì agent sẽ mất hoàn toàn context về ngày phép và ngưỡng khóa tài khoản.

Mỗi rule chỉ kích hoạt khi `doc_id` khớp đúng nguồn (`hr_leave_policy` hoặc `it_helpdesk_faq`) để tránh false positive trên các tài liệu khác. Sau khi sửa, tôi append tag `[cleaned: tên_rule]` vào cuối chunk_text để dễ trace trong CSV cleaned mà không ảnh hưởng đến nội dung chính. `metric_impact` được ghi động bằng list `impacts` — nếu một row kích hoạt nhiều rule cùng lúc, tất cả đều được ghi, tránh mất thông tin khi phân tích sau.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Khi viết Rule 5 (`fix_sick_leave_stale`), tôi phát hiện regex ban đầu `\b(5|7)\s*ngày\s*nghỉ\s*ốm\b` có thể khớp nhầm với văn bản hợp lệ nếu câu đang nói về "hơn 5 ngày nghỉ ốm cần giấy tờ y tế" — đây là nội dung đúng trong `hr_leave_policy.txt` mục 1.2.

Tôi kiểm tra lại file nguồn và nhận ra câu gốc là *"Nếu nghỉ trên 3 ngày liên tiếp"*, không chứa cụm "5 ngày nghỉ ốm" nên regex không khớp nhầm. Tuy nhiên để an toàn, tôi đã test thủ công bằng cách chạy trực tiếp `_replace_sick_leave_stale()` trên các câu từ file `.txt` gốc và xác nhận không có false positive trước khi tích hợp vào `clean_rows()`. Đây là bước kiểm tra nhỏ nhưng quan trọng trước khi chạy pipeline đầy đủ.

---

## 4. Bằng chứng trước / sau (80–120 từ)

Sau khi chạy `python etl_pipeline.py run --run-id sprint2-clean`, file cleaned tại `artifacts/cleaned/cleaned_sprint2-clean.csv` có các dòng chứng minh rule kích hoạt:

**run_id = sprint2-inject** — `raw_records=13`, `cleaned_records=9`, `quarantine_records=4`

Bằng chứng thực tế từ `artifacts/cleaned/cleaned_sprint2-inject.csv`, cả 3 rule mới đều kích hoạt:

```
# Rule 4: fix_leave_10_to_12
hr_leave_policy_7_403544517cff2566,hr_leave_policy,
"Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm. [cleaned: stale_leave_days]",
2026-02-01,2026-04-10T08:00:00

# Rule 5: fix_sick_leave_stale
hr_leave_policy_8_4948372b4dca5038,hr_leave_policy,
"Nhân viên được 10 ngày nghỉ ốm có trả lương mỗi năm (bản cũ). [cleaned: stale_sick_leave]",
2026-02-01,2026-04-10T08:00:00

# Rule 6: fix_lockout_threshold_stale
it_helpdesk_faq_9_c0ce6ec985a766e2,it_helpdesk_faq,
"Tài khoản bị khóa sau 5 lần đăng nhập sai liên tiếp (cấu hình cũ). [cleaned: stale_lockout_threshold]",
2026-02-01,2026-04-10T08:00:00
```

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ đọc ngưỡng cutoff (`HR_MIN_EFFECTIVE_DATE`, giá trị đúng trong các rule) từ `contracts/data_contract.yaml` thay vì hard-code trong file Python. Cách này cho phép thay đổi chính sách mà không cần sửa code — inject một cutoff khác vào contract là đủ để thay đổi quyết định clean, đáp ứng tiêu chí **Distinction (d)** trong SCORING.
