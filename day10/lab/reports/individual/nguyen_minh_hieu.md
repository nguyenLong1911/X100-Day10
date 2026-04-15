# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Minh Hiếu  
**Vai trò:** Embed / Eval Owner — phụ trách phần eval retrieval của Sprint 3  
**Ngày nộp:** 2026-04-15  
**Độ dài yêu cầu:** **400–650 từ**

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Lưu: `reports/individual/nguyen_minh_hieu.md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `eval_retrieval.py` (chạy before/after trên top-k đã embed)
- Artifacts kiểm chứng: `artifacts/eval/after_inject_bad.csv`, `artifacts/eval/before_after_eval.csv`, `artifacts/eval/eval_good.csv`
- Log tham chiếu: `artifacts/logs/run_sprint3-before.log`, `artifacts/logs/run_inject-bad.log`

**Kết nối với thành viên khác:**

Tôi không đụng phần embed của Sprint 3 — bạn Embed Owner đã chạy `etl_pipeline.py run --run-id sprint3-before` và `--run-id inject-bad` với cờ `--no-refund-fix --skip-validate` để đẩy dữ liệu xấu lên collection `day10_kb`. Tôi nhận collection đó làm đầu vào, chạy `eval_retrieval.py` để sinh bộ CSV before/after, rồi chuyển kết quả lại cho bạn Monitoring/Docs ghép vào `quality_report.md` và `group_report.md`.

**Bằng chứng (commit / comment trong code):**

Log `run_sprint3-before.log` xác nhận `embed_upsert count=6 collection=day10_kb` và `embed_prune_removed=1` — nghĩa là collection mà tôi eval đúng là bản stale refund. Sau run khôi phục, `before_after_eval.csv` đạt `hits_forbidden=no` cho `q_refund_window`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định kỹ thuật của tôi là **eval trên toàn bộ top-k chứ không chỉ top-1**, đúng tinh thần ghi chú của README (`hits_forbidden` quét top-k ghép lại). Lý do: trong run `inject-bad`, top1_preview của `q_refund_window` vẫn chứa câu “7 ngày” nhìn có vẻ đúng, nhưng khi quét cả top-k thì phát hiện chunk stale “14 ngày làm việc” vẫn lọt vào context. Nếu tôi chỉ tin top-1 như một số framework mặc định, chỉ số `contains_expected=yes` sẽ che mất lỗi publish boundary. Tôi giữ `top_k_used=3` cho cả 4 câu hỏi để cột `hits_forbidden` trở thành tín hiệu observability thực sự — một chunk cũ cũng đủ để đánh fail, giống cách prod RAG bị user “bắt bài” khi agent đọc nhầm version.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Anomaly tôi xử lý là sự **bất đối xứng giữa top1 và top-k** trên câu `q_refund_window` ở run `inject-bad`. Triệu chứng: trong `after_inject_bad.csv`, dòng `q_refund_window` có `contains_expected=yes` (câu trả lời “nhìn đúng”) nhưng `hits_forbidden=yes` và `top1_preview` lại chứa nguyên cụm “Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn (ghi chú: bản sync cũ policy-v3 — lỗi migration)”. Check phát hiện là cột `hits_forbidden` do tôi cấu hình quét top-k. Fix: tôi không sửa collection (việc đó thuộc embed), mà phối hợp với bạn Embed chạy lại pipeline chuẩn (không `--no-refund-fix`), sau đó eval lại để đưa ra `before_after_eval.csv`. Kết quả: cùng câu `q_refund_window`, `hits_forbidden` chuyển từ `yes` → `no` và `top1_preview` sạch, xác nhận fix có hiệu lực đến tận publish boundary.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Before (run `inject-bad`, file `artifacts/eval/after_inject_bad.csv`):**

- `q_refund_window,...,policy_refund_v4,"Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn (ghi chú: bản sync cũ policy-v3 — lỗi migration).",yes,yes,,3`

**After (run khôi phục, file `artifacts/eval/before_after_eval.csv`):**

- `q_refund_window,...,policy_refund_v4,"Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.",yes,no,,3`

Merit cho `q_leave_version`: cả hai file đều cho `top1_doc_id=hr_leave_policy`, `top1_doc_expected=yes`, `hits_forbidden=no` — chứng tỏ quarantine HR cũ (10 ngày) giữ vững qua cả hai kịch bản, không bị inject refund làm nhiễu.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ thêm flag `--scenario` cho `eval_retrieval.py` để xuất 1 file duy nhất có cột `scenario` (before/after) thay vì 2 file rời, kèm cột `top_k_previews` liệt kê đầy đủ 3 chunk. Việc này giúp reviewer thấy ngay chunk stale nằm ở rank thứ mấy, thay vì phải mở log embed để truy.
