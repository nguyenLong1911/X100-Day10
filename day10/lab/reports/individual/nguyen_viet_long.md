# Báo cáo cá nhân — Nguyễn Việt Long

**Họ và tên:** Nguyễn Việt Long  
**Vai trò:** Embed Owner  
**Độ dài:** ~500 từ

---

## 1. Phụ trách

Tôi đảm nhận vai trò **Embed Owner**, chịu trách nhiệm toàn bộ lớp embedding trong pipeline ETL: từ kết nối ChromaDB, tạo embedding function, đảm bảo idempotency khi upsert, đến prune vector cũ và chạy eval retrieval.

**Các file tôi tạo / sửa (commit `da2c9aa`):**

- **`embedding_helper.py`** (tạo mới, 91 dòng): Module trung tâm cung cấp `get_chroma_client()`, `get_embedding_function()`, `get_collection_name()` và class `ShopAIKeyEmbeddingFunction` — dùng chung cho `etl_pipeline.py`, `eval_retrieval.py`, `grading_run.py`.
- **`etl_pipeline.py`** (sửa hàm `cmd_embed_internal`): Refactor để import từ `embedding_helper` thay vì hard-code `SentenceTransformerEmbeddingFunction`, giữ nguyên logic prune + upsert idempotent.
- **`eval_retrieval.py`** (sửa): Chuyển sang dùng `get_chroma_client()`, `get_embedding_function()` từ helper — đảm bảo eval và pipeline dùng cùng embedding function.
- **`grading_run.py`** (sửa): Tương tự, thống nhất embedding function qua helper.
- **`test_embed_owner.py`** (tạo mới, 309 dòng): Test suite gồm 6 test case kiểm tra env, embedding function, Chroma collection, idempotent upsert, prune stale IDs, và query retrieval.
- **`.env.example`** (sửa): Thêm biến `SHOPAIKEY_API_KEY` và `OPENAI_EMBEDDING_MODEL` để hỗ trợ ShopAIKey API.
- **Artifacts:** 4 lượt chạy pipeline (`test-v2`, `test-v2-rerun`, `test-embed-owner`, `test-embed-owner-2`) tạo cleaned CSV, quarantine CSV, manifests, và `before_after_eval.csv`.

---

## 2. Quyết định kỹ thuật

**ShopAIKey API vs SentenceTransformer local — strategy fallback:**

Baseline ban đầu hard-code `SentenceTransformerEmbeddingFunction` ở 3 file (`etl_pipeline.py`, `eval_retrieval.py`, `grading_run.py`). Vấn đề: embedding dimension không nhất quán nếu một thành viên dùng model khác, và không tận dụng được API key nhóm đã có.

Tôi quyết định tạo `embedding_helper.py` làm **single source of truth**: nếu `SHOPAIKEY_API_KEY` tồn tại trong `.env` → dùng `ShopAIKeyEmbeddingFunction` gọi API OpenAI-compatible (`text-embedding-3-small`); nếu không → fallback `SentenceTransformerEmbeddingFunction` local. Class `ShopAIKeyEmbeddingFunction` implement đủ protocol ChromaDB (`__call__`, `name()`, `get_config()`, `build_from_config()`) để tương thích phiên bản ChromaDB ≥ 1.5. Nhờ vậy cả 3 entrypoint (`etl_pipeline`, `eval_retrieval`, `grading_run`) đều nhất quán embedding — tránh lỗi dimension mismatch khi query.

---

## 3. Sự cố / anomaly

Khi chạy `test-v2` lần đầu rồi chạy lại `test-v2-rerun` (cùng dữ liệu cleaned), tôi phát hiện collection count không đổi (`count=6` cả 2 lần) — **upsert idempotent hoạt động đúng**. Tuy nhiên, khi thử bỏ logic prune (comment `col.delete(ids=drop)`) rồi inject dữ liệu khác, `before_after_eval.csv` vẫn trả về vector cũ ở top-k → `hits_forbidden` có khả năng sai. Fix: giữ nguyên prune — so sánh `prev_ids` vs `ids` hiện tại, xóa id không còn trong cleaned run trước khi upsert. Log ghi `embed_prune_removed=N` khi có vector bị xóa.

---

## 4. Before/after

**Manifest (run `test-embed-owner`):** `raw_records=10`, `cleaned_records=6`, `quarantine_records=4` — pipeline exit 0, expectation pass.

**Eval CSV (`before_after_eval.csv`):**
- `q_refund_window`: `contains_expected=yes`, `hits_forbidden=no` — trả đúng "7 ngày".
- `q_leave_version`: `contains_expected=yes`, `hits_forbidden=no`, `top1_doc_expected=yes` — trả đúng "12 ngày phép" theo chính sách 2026.

**Idempotency:** Chạy `test-v2` → `test-v2-rerun`, count collection giữ nguyên 6, không phình tài nguyên.

---

## 5. Cải tiến thêm 2 giờ

Viết `test_embed_owner.py` với 6 test tự động (env check, embedding function, Chroma collection, idempotent upsert, prune stale IDs, query retrieval) — chạy `python test_embed_owner.py` để verify toàn bộ lớp embed trước khi merge, giúp nhóm phát hiện sớm lỗi cấu hình hoặc API key hết hạn.
