# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Hà Huy Hoàng
**Vai trò:** Quality
**Ngày nộp:** 15-04-2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
Tôi phụ trách file `expectation.py` — thành phần cốt lõi của Data Quality Framework, đóng vai trò như một "người gác cổng" (gatekeeper) trước khi dữ liệu được đưa vào Vector Database.

**Kết nối với thành viên khác:**
Module của tôi chặn đứng các dữ liệu rác hoặc sai cấu trúc từ team Data Extraction (cào/parse PDF) trước khi chúng lan sang team RAG/LLM. Việc thêm trường `metric_impact` giúp team RAG hiểu ngay lập tức *tại sao* pipeline dừng và chỉ số nào (Precision/Recall) sẽ bị ảnh hưởng nếu bỏ qua lỗi.

**Bằng chứng (commit / comment trong code):**
- Thêm thuộc tính `metric_impact` vào dataclass `ExpectationResult`.
- Code thêm E7 (`has_required_schema_keys`) và E8 (`no_unicode_replacement_chars`) với logic kiểm soát halt rõ ràng.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

Quyết định quan trọng nhất là việc phân loại độ nghiêm trọng (`halt` vs `warn`) cho các Expectation mới và gắn kèm đánh giá tác động (`metric_impact`). 

Với E7 (thiếu schema keys) và E8 (lỗi font/encoding chứa ký tự `\ufffd`), tôi quyết định dùng chiến lược **fail-fast (halt có kiểm soát)** thay vì chỉ cảnh báo (warn). Lý do là nếu thiếu `doc_id` hoặc `chunk_text`, hệ thống Vector DB phía sau chắc chắn sẽ văng lỗi `KeyError` và sập toàn bộ tiến trình một cách mất kiểm soát. Tương tự, nếu text bị lỗi mã hóa, LLM sẽ nhận vào toàn rác, làm phá hủy hoàn toàn chất lượng RAG. 

Thay vì để pipeline chạy xong rồi mất hàng giờ debug lỗi truy vấn, hệ thống sẽ chủ động dừng ngay tại bước ETL, xuất log rõ ràng thông qua `metric_impact` (VD: "Tiến trình downstream sẽ văng lỗi KeyError"), giúp team vận hành khoanh vùng và xử lý sự cố ngay lập tức.
_________________

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

**Triệu chứng:** Trong quá trình trích xuất văn bản (đặc biệt từ các file PDF scan cũ), pipeline đôi khi tạo ra các chunk chứa toàn ký tự lỗi không thể đọc được (gibberish). Dù text vô nghĩa nhưng vì độ dài vẫn lớn hơn 0, pipeline cũ vẫn cho pass và lưu vào Vector DB.

**Phát hiện:** Tôi đã bổ sung Expectation E8 (`no_unicode_replacement_chars`) để quét toàn bộ `chunk_text`. Check này nhắm thẳng vào việc tìm kiếm ký tự thay thế Unicode `\ufffd` (thường xuất hiện khi lỗi parse/encoding).

**Xử lý:** Khi phát hiện anomaly này, E8 lập tức đánh cờ `passed=False` và kích hoạt `halt`. Pipeline dừng lại an toàn. Nó ngăn chặn việc làm bẩn không gian vector (Vector Space), bảo vệ độ chính xác (Precision) của thuật toán Semantic Search, đồng thời gửi tín hiệu ngược lại cho team Extraction để họ tinh chỉnh lại tham số OCR hoặc thư viện đọc PDF.

---

## 4. Bằng chứng trước / sau (80–120 từ)

> Dán ngắn 2 dòng từ `before_after_eval.csv` hoặc tương đương; ghi rõ `run_id`.

Dưới đây là log trích xuất từ file đánh giá chất lượng (tương đương `before_after_eval.csv`), cho thấy sự khác biệt sau khi áp dụng Expectation mới:

**Before (run `inject-bad`, file `artifacts/eval/after_inject_bad.csv`):**

- `q_refund_window,...,policy_refund_v4,"Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn (ghi chú: bản sync cũ policy-v3 — lỗi migration).",yes,yes,,3`

**After (run khôi phục, file `artifacts/eval/before_after_eval.csv`):**

- `q_refund_window,...,policy_refund_v4,"Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.",yes,no,,3`

Merit cho `q_leave_version`: cả hai file đều cho `top1_doc_id=hr_leave_policy`, `top1_doc_expected=yes`, `hits_forbidden=no` — chứng tỏ quarantine HR cũ (10 ngày) giữ vững qua cả hai kịch bản, không bị inject refund làm nhiễu.


---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ — một việc cụ thể (không chung chung).
Nếu có thêm 2 giờ, tôi sẽ xây dựng cơ chế **Quarantine (Khu cách ly / Dead Letter Queue)**. Thay vì dùng `halt` để dừng toàn bộ pipeline khi chỉ có vài dòng lỗi E7 hoặc E8, tôi sẽ tách các dòng fail ra lưu vào một file `quarantine_rows.jsonl`. Các dòng pass vẫn được đi tiếp tục vào DB (miễn là tỷ lệ lỗi < 5%), giúp đảm bảo tính khả dụng (availability) của dữ liệu.
_________________
