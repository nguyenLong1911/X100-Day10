# Quality report — Lab Day 10 (nhóm)

**run_id (good):** `sprint4-redo-vi`  
**run_id (bad):** `sprint3-redo-bad`  
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (sprint3-redo-bad) | Sau (sprint4-redo-vi) | Ghi chú |
|--------|---------------------------|------------------------|---------|
| raw_records | 10 | 10 | Cùng file `data/raw/policy_export_dirty.csv` |
| cleaned_records | 6 | 6 | Rule clean giữ ổn định volume |
| quarantine_records | 4 | 4 | Các dòng bẩn bị cách ly |
| Expectation halt? | **FAIL** `refund_no_stale_14d_window` (`violations=1`) nhưng được override bằng `--skip-validate` | OK toàn bộ expectation | Đúng kịch bản Sprint 3 inject rồi recover |

Nguồn:
- `artifacts/logs/run_sprint3-redo-bad.log`
- `artifacts/logs/run_sprint4-redo-vi.log`

---

## 2. Before / after retrieval (bắt buộc)

Dữ liệu eval:
- Trước (bad): `artifacts/eval/after_inject_bad.csv`
- Sau (good): `artifacts/eval/before_after_eval.csv`

### Câu hỏi then chốt — `q_refund_window`

> Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?

**Trước (bad):**
```text
top1_doc_id=policy_refund_v4
top1_preview=...14 ngày làm việc...
contains_expected=yes
hits_forbidden=yes
```

**Sau (good):**
```text
top1_doc_id=policy_refund_v4
top1_preview=...7 ngày làm việc...
contains_expected=yes
hits_forbidden=no
```

Kết luận: inject bad đã để lọt chunk stale vào top-k. Sau recover, stale chunk được loại bỏ và `hits_forbidden` đổi từ `yes -> no`.

### Merit — `q_leave_version` (HR 10 vs 12 ngày phép)

| Trường | Trước (bad) | Sau (good) |
|--------|-------------|------------|
| top1_doc_id | hr_leave_policy | hr_leave_policy |
| contains_expected | yes | yes |
| hits_forbidden | no | no |
| top1_doc_expected | yes | yes |

---

## 3. Freshness & monitor

Kết quả freshness ở run good:

```text
freshness_check=FAIL
latest_exported_at=2026-04-10T08:00:00
age_hours=122.436
sla_hours=24.0
reason=freshness_sla_exceeded
```

Giải thích: dữ liệu raw mẫu có timestamp cũ hơn SLA 24h, nên freshness FAIL là hợp lý. Pipeline vẫn `PIPELINE_OK`; đây là tín hiệu vận hành, không phải lỗi ETL.

---

## 4. Corruption inject (Sprint 3)

Lệnh inject đã dùng:

```bash
python etl_pipeline.py run --run-id sprint3-redo-bad --no-refund-fix --skip-validate
```

Phát hiện qua 2 lớp:
1. Expectation halt fail: `refund_no_stale_14d_window` (`violations=1`).
2. Eval retrieval cho `q_refund_window` có `hits_forbidden=yes`.

Khắc phục:

```bash
python etl_pipeline.py run --run-id sprint4-redo-vi
python eval_retrieval.py --questions data/test_questions.json --out artifacts/eval/before_after_eval.csv --top-k 3
```

Sau khắc phục: `hits_forbidden=no` cho `q_refund_window`.

---

## 5. Kết quả grading_questions

Lệnh chấm:

```bash
python grading_run.py --questions data/grading_questions.json --out artifacts/eval/grading_run.jsonl --top-k 5
```

Kết quả `artifacts/eval/grading_run.jsonl`:
- `gq_d10_01`: `contains_expected=true`, `hits_forbidden=false`
- `gq_d10_02`: `contains_expected=true`
- `gq_d10_03`: `contains_expected=true`, `hits_forbidden=false`, `top1_doc_matches=true`

Kiểm tra nhanh:

```bash
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl --manifest artifacts/manifests/manifest_sprint4-redo-vi.json
```

Tất cả `MERIT_CHECK[...]` đều `OK`.

---

## 6. Hạn chế & việc chưa làm

- Chưa có dashboard time-series cho freshness + `hits_forbidden`.
- Chưa đo freshness ở 2 boundary (ingest + publish) để lấy bonus Distinction.
- Chưa mở rộng bộ eval > 4 test questions để stress test retrieval.
