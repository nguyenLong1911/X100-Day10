# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** X100  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Nguyễn Lâm Tùng | Ingestion / Raw Owner | nguyenlamtung2005@gmail.com |
| Trần Gia Khánh | Ingestion / Raw Owner | giakhanh28031995@gmail.com |
| Tống Tiến Mạnh | Cleaning & Quality Owner | tienmanhttm2018@gmail.com |
| Hà Huy Hoàng | Cleaning & Quality Owner | masterjtrhoang171110x@gmail.com |
| Nguyễn Minh Hiếu | Embed & Idempotency Owner | nguyenhieu16072004@gmail.com |
| Nguyễn Việt Long | Embed & Idempotency Owner | nguyenvietlong9k@gmail.com |
| Nguyễn Quang Đăng | Monitoring / Docs Owner | dangnguyen12a@gmail.com |

**Ngày nộp:** 15/04/2026  
**Repo:** https://github.com/nguyenLong1911/X100-Day10  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Nhóm triển khai pipeline dữ liệu theo thứ tự ingest -> clean -> validate -> embed -> monitor trong `etl_pipeline.py`. Nguồn raw chính là `data/raw/policy_export_dirty.csv`, chứa cả dữ liệu hợp lệ và dữ liệu lỗi có chủ đích để kiểm thử observability (duplicate, stale refund, dòng thiếu dữ liệu, định dạng ngày không chuẩn, xung đột version HR). Sau bước clean, pipeline sinh hai đầu ra: `cleaned_csv` để publish vào Chroma và `quarantine_csv` để lưu các dòng bị loại. Tiếp theo hệ thống chạy expectation suite với cơ chế `halt/warn`; nếu expectation mức halt fail thì dừng pipeline (trừ run inject có chủ đích dùng `--skip-validate`). Khi expectation pass, hệ thống embed vào collection `day10_kb_sprint1`, ghi manifest và chạy freshness check. Sau cùng, nhóm dùng `eval_retrieval.py` và `grading_run.py` để đo chất lượng retrieval và chấm câu grading. Mỗi lần chạy đều có `run_id`, số lượng record, đường dẫn artifact và trạng thái freshness để đảm bảo trace end-to-end.

**Lệnh chạy một dòng (copy từ workflow nhóm):**

`CHROMA_DB_PATH=./chroma_db_sprint1 CHROMA_COLLECTION=day10_kb_sprint1 python etl_pipeline.py run --run-id sprint4-redo-vi`

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| has_required_schema_keys (halt) | rows_missing_keys=0 | rows_missing_keys=0 | `artifacts/logs/run_sprint4-redo-vi.log` |
| no_unicode_replacement_chars (halt) | corrupted_rows=0 | corrupted_rows=0 | `artifacts/logs/run_sprint4-redo-vi.log` |
| refund_no_stale_14d_window (halt) | violations=0 (good) | violations=1 (inject bad) | `artifacts/logs/run_sprint3-redo-bad.log`, `artifacts/eval/after_inject_bad.csv` |

**Rule chính (baseline + mở rộng):**

- allowlist `doc_id`: chỉ cho đi tiếp các tài liệu thuộc bộ nguồn hợp lệ
- chuẩn hóa `effective_date` về định dạng ISO để tránh lỗi metadata filtering
- quarantine bản HR cũ theo cutoff version (`hr_leave_policy`)
- dedupe theo `(doc_id, normalized_chunk_text)` để chống phình index
- fix stale refund window `14 -> 7` cho `policy_refund_v4`

**Ví dụ 1 lần expectation fail và cách xử lý:**

Ở run `sprint3-redo-bad`, nhóm chủ động tắt refund fix (`--no-refund-fix`) nên expectation `refund_no_stale_14d_window` fail với `violations=1`. Nhóm vẫn cho chạy tiếp bằng `--skip-validate` để tạo bằng chứng Sprint 3. Sau đó chạy lại pipeline chuẩn `sprint4-redo-vi` không có cờ inject, expectation quay lại trạng thái OK toàn bộ.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Nhóm chạy kịch bản xấu có chủ đích:

`python etl_pipeline.py run --run-id sprint3-redo-bad --no-refund-fix --skip-validate`

Sau đó chạy eval:

`python eval_retrieval.py --questions data/test_questions.json --out artifacts/eval/after_inject_bad.csv --top-k 3`

Để khôi phục, nhóm chạy lại pipeline chuẩn:

`python etl_pipeline.py run --run-id sprint4-redo-vi`

và eval lại:

`python eval_retrieval.py --questions data/test_questions.json --out artifacts/eval/before_after_eval.csv --top-k 3`

**Kết quả định lượng (từ CSV / bảng):**

- `q_refund_window`:
	- bad: `contains_expected=yes`, `hits_forbidden=yes`, top1 chứa cụm `14 ngày làm việc`
	- good: `contains_expected=yes`, `hits_forbidden=no`, top1 chứa `7 ngày làm việc`
- `q_leave_version`:
	- bad và good đều `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes`

Kết quả chứng minh rõ inject làm retrieval tệ đi ở câu refund, và pipeline chuẩn khôi phục chất lượng sau khi bật lại quality gate.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

Nhóm dùng SLA mặc định `FRESHNESS_SLA_HOURS=24`. Trong run tốt `sprint4-redo-vi`, freshness check trả về FAIL vì `latest_exported_at=2026-04-10T08:00:00`, `age_hours=122.436`, vượt ngưỡng 24 giờ. Điều này phù hợp với dữ liệu lab (snapshot cố ý cũ), không phải lỗi pipeline vì log vẫn có `PIPELINE_OK`. Về vận hành, nhóm quy ước: PASS nghĩa là đủ điều kiện publish cho agent, WARN là thiếu tín hiệu/thiếu timestamp cần kiểm tra, FAIL là dữ liệu stale và phải re-export trước khi dùng cho sản phẩm thật. Ngoài ra, nhóm đã chạy `instructor_quick_check.py` cho manifest mới để xác nhận đủ `run_id`, `raw`, `clean`, `quarantine`.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Dữ liệu đã clean và embed ở Day 10 là tầng đầu vào cho retrieval của Day 09. Nhóm tách collection `day10_kb_sprint1` để tránh lẫn với dữ liệu cũ, giúp so sánh before/after rõ ràng theo run_id. Khi quality gate pass và eval ổn định, collection này có thể được promote để cấp ngữ cảnh cho multi-agent flow của Day 09 mà không cần đổi logic worker.

---

## 6. Rủi ro còn lại & việc chưa làm

- Chưa có dashboard time-series cho freshness và `hits_forbidden`.
- Chưa đo freshness ở 2 boundary (ingest + publish) để lấy bonus Distinction.
- Chưa mở rộng bộ eval thành nhiều câu theo từng slice policy để stress test.
- Chưa tích hợp auto-run grading/eval vào CI sau mỗi lần cập nhật cleaning rule.
