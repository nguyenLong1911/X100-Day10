# Quality report — Lab Day 10 (nhóm)

**run_id (good):** `sprint3-good`
**run_id (bad):** `inject-bad`
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (sprint3-good) | Ghi chú |
|--------|--------------------|---------------------|---------|
| raw_records | 10 | 10 | Cùng file `data/raw/policy_export_dirty.csv` |
| cleaned_records | 6 | 6 | Rule dedupe + allowlist + quarantine không đổi số dòng |
| quarantine_records | 4 | 4 | Cùng 4 dòng bẩn bị loại |
| Expectation halt? | **FAIL** `refund_no_stale_14d_window` (violations=1) — bỏ qua bằng `--skip-validate` | OK toàn bộ | Bad run dùng `--no-refund-fix --skip-validate` để cố ý embed chunk stale |

Nguồn: [run_inject-bad.log](../artifacts/logs/run_inject-bad.log), [run_sprint3-good.log](../artifacts/logs/run_sprint3-good.log)

---

## 2. Before / after retrieval (bắt buộc)

Dữ liệu eval:
- Trước (bad): [artifacts/eval/after_inject_bad.csv](../artifacts/eval/after_inject_bad.csv)
- Sau (good): [artifacts/eval/before_after_eval.csv](../artifacts/eval/before_after_eval.csv)

### Câu hỏi then chốt — `q_refund_window`

> "Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền kể từ khi xác nhận đơn?"

**Trước (inject-bad):**
```
top1_doc_id=policy_refund_v4
top1_preview=Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn (ghi chú: bản sync cũ policy-v3 — lỗi migration).
contains_expected=yes
hits_forbidden=yes     ← TOP-K VẪN DÍNH CHUNK "14 NGÀY" STALE
```

**Sau (sprint3-good):**
```
top1_doc_id=policy_refund_v4
top1_preview=Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.
contains_expected=yes
hits_forbidden=no      ← ĐÃ SẠCH, KHÔNG CÒN CHUNK STALE TRONG TOP-K
```

**Kết luận:** Trước fix, top-k ghép lại vẫn chứa cụm "14 ngày" — agent hoặc user có thể trả lời sai theo version cũ. Sau khi chạy lại pipeline chuẩn (refund fix bật, expectation pass, embed upsert + prune), chunk stale đã bị xoá khỏi collection. `hits_forbidden` chuyển từ **yes → no** đúng tinh thần slide Day 10: "observability phải quét toàn bộ top-k, không chỉ top-1".

### Merit — `q_leave_version` (HR 10 vs 12 ngày phép)

| Trường | Trước (bad) | Sau (good) |
|--------|-------------|------------|
| top1_doc_id | hr_leave_policy | hr_leave_policy |
| contains_expected | yes | yes |
| hits_forbidden | no | no |
| top1_doc_expected | **yes** | **yes** |

Cả bad và good đều không bị dính version "10 ngày" vì expectation `hr_leave_no_stale_10d_annual` chặn từ tầng cleaning/quarantine (không phụ thuộc cờ `--no-refund-fix`), và dòng HR version cũ đã bị quarantine ở cả 2 run. Tức là rule HR version đã bảo vệ được retrieval **ngay cả khi sinh viên cố ý inject refund stale** — chứng minh 2 rule độc lập nhau, không false-positive chéo.

---

## 3. Freshness & monitor

```
freshness_check=FAIL
latest_exported_at=2026-04-10T08:00:00
age_hours≈120.6
sla_hours=24.0
reason=freshness_sla_exceeded
```

Nguồn: [run_sprint3-good.log:16](../artifacts/logs/run_sprint3-good.log#L16).

**Giải thích:** File raw export đã ~5 ngày, vượt SLA 24h nên `freshness_check` báo FAIL. Đây là **WARN nghiệp vụ** chứ không phải lỗi pipeline — pipeline vẫn `PIPELINE_OK` và publish được, nhưng runbook yêu cầu owner re-export nguồn trước khi trả kết quả cho agent Day 09. Xem [runbook.md](runbook.md) cho SLA mapping.

---

## 4. Corruption inject (Sprint 3)

**Cách inject:** dùng flag có sẵn của `etl_pipeline.py`:

```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

- `--no-refund-fix`: bỏ qua rule fix refund window 14 → 7 ngày trong [transform/cleaning_rules.py](../transform/cleaning_rules.py) → chunk `policy_refund_v4` giữ nguyên câu "14 ngày làm việc" (đúng version stale v3).
- `--skip-validate`: cho phép tiếp tục embed dù expectation `refund_no_stale_14d_window` FAIL (violations=1) — giả lập kịch bản "ai đó bấm override halt".

**Cách phát hiện:**

1. **Expectation halt** ([run_inject-bad.log:9](../artifacts/logs/run_inject-bad.log#L9)) — `refund_no_stale_14d_window` FAIL ngay tại tầng quality, trước khi vào embed. Nếu không có `--skip-validate` thì pipeline đã halt exit 1.
2. **Retrieval eval `hits_forbidden=yes`** cho `q_refund_window` — quét toàn bộ top-k, phát hiện chunk "14 ngày" vẫn có trong collection. Đây là tuyến phòng thủ thứ 2 (observability tầng publish) trong trường hợp tầng expectation bị bypass.
3. **Manifest so sánh** — `manifest_inject-bad.json` vs `manifest_sprint3-good.json` có thể diff `cleaned_csv` hash để biết dữ liệu thay đổi (debug order theo slide Day 10: freshness → volume → schema → lineage).

**Đã khôi phục:** chạy lại `python etl_pipeline.py run --run-id sprint3-good` (không flag inject) để embed upsert + prune chunk cũ — xác nhận `embed_prune_removed=1` ở [run_sprint3-good.log:13](../artifacts/logs/run_sprint3-good.log#L13), nghĩa là chunk stale "14 ngày" đã bị xoá khỏi Chroma.

---

## 5. Hạn chế & việc chưa làm

- Chưa chạy `grading_run.py` (chờ sau 17:00 theo README).
- Chưa có dashboard theo dõi `hits_forbidden` theo thời gian — hiện chỉ là 1-shot CSV so sánh.
- Freshness SLA đang hard-code 24h trong `monitoring/freshness_check.py`; nên đẩy vào `contracts/data_contract.yaml` để đổi không cần sửa code.
- Chưa test inject nhiều kiểu bẩn cùng lúc (ví dụ: BOM + HR stale + refund stale) để xem expectation nào halt trước.
