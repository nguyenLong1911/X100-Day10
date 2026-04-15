# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Lâm Tùng  
**Mã sinh viên:** 2A202600173  
**Vai trò:** Embed & Idempotency Owner  
**Ngày nộp:** 15/04/2026  

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `embedding_helper.py` — viết wrapper embedding function dùng chung cho toàn pipeline (ShopAIKey OpenAI-compatible API với fallback SentenceTransformer local).
- `etl_pipeline.py` — tích hợp embedding function mới vào hàm `cmd_embed_internal`, đảm bảo idempotent upsert theo `chunk_id` và prune vector cũ không còn trong cleaned run.
- `eval_retrieval.py`, `grading_run.py` — cập nhật import để sử dụng `embedding_helper` thống nhất.
- `contracts/data_contract.yaml` — điền `owner_team`, `alert_channel`.
- `docs/data_contract.md` — bổ sung schema cleaned và mô tả source map.

**Kết nối với thành viên khác:**

Tôi nhận cleaned CSV từ Cleaning Owner (output `clean_rows`), embed vào ChromaDB, và cung cấp collection cho eval retrieval. Tôi cũng merge branch `embed` của thành viên Long vào branch `khanh`, giải quyết conflict giữa `embedding_utils.py` và `embedding_helper.py`.

**Bằng chứng:** commit `5cc5f19` (Tung sprint1), commit `b7b5e18` (merge main into khanh).

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi quyết định thay thế SentenceTransformer local bằng OpenAI-compatible embedding qua ShopAIKey API (`text-embedding-3-small`). Lý do: model local `all-MiniLM-L6-v2` (~90MB) yêu cầu tải lần đầu và chất lượng embedding tiếng Việt hạn chế. `text-embedding-3-small` xử lý tiếng Việt tốt hơn, giúp retrieval chính xác hơn trên corpus policy/HR của lab.

Tôi thiết kế `embedding_helper.py` với pattern fallback: nếu `SHOPAIKEY_API_KEY` tồn tại trong `.env` thì dùng API, ngược lại fallback về SentenceTransformer. Điều này đảm bảo pipeline không bị break khi chạy offline hoặc không có API key. Class `ShopAIKeyEmbeddingFunction` implement đủ protocol ChromaDB (`__call__`, `name`, `get_config`, `build_from_config`) để tương thích hoàn toàn với `get_or_create_collection`.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Khi merge branch `embed` (commit `da2c9aa` của Long) vào branch `khanh`, xảy ra conflict giữa `embedding_utils.py` (tôi tạo ban đầu) và `embedding_helper.py` (Long tạo trên main). Cả hai file đều wrap ChromaDB client nhưng khác interface. Pipeline bị fail vì `etl_pipeline.py` import cả hai module.

Tôi phát hiện lỗi qua `git merge` conflict marker, sau đó quyết định giữ `embedding_helper.py` (vì đã có fallback logic hoàn chỉnh hơn) và xóa `embedding_utils.py`. Cập nhật lại import trong `etl_pipeline.py`, `eval_retrieval.py`, `grading_run.py` để dùng thống nhất `from embedding_helper import ...`. Chạy lại pipeline với `run_id=merge-test` — exit 0, 6 expectations OK, embed upsert 6 chunks thành công (log: `run_merge-test.log`).

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Run chuẩn (`run_id=merge-test`):**

```
raw_records=10 → cleaned_records=6, quarantine_records=4
expectation[refund_no_stale_14d_window] OK (halt) :: violations=0
embed_upsert count=6 collection=day10_kb
```

**Eval retrieval (`before_after_eval.csv`):**

| question_id | top1_doc_id | contains_expected | hits_forbidden |
|-------------|-------------|-------------------|----------------|
| q_refund_window | policy_refund_v4 | yes | no |
| q_p1_sla | sla_p1_2026 | yes | no |
| q_lockout | it_helpdesk_faq | yes | no |
| q_leave_version | hr_leave_policy | yes | no |

Tất cả 4 câu retrieval đều trả đúng `contains_expected=yes` và `hits_forbidden=no`, chứng minh pipeline clean + embed hoạt động chính xác. Câu `q_leave_version` có `top1_doc_expected=yes` — bản HR 2026 (12 ngày phép) được ưu tiên, bản HR 2025 (10 ngày phép) đã bị quarantine.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ implement **batch embedding với retry logic** trong `embedding_helper.py` — hiện tại nếu API rate limit hoặc timeout giữa chừng, toàn bộ upsert fail mà không có checkpoint. Tôi sẽ chia chunks thành batch 50, retry mỗi batch tối đa 3 lần với exponential backoff, và ghi log batch nào đã embed thành công để resume từ đó khi rerun.
