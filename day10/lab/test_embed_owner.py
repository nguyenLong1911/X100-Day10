#!/usr/bin/env python3
"""
Test độc lập cho phần Embed Owner — Chroma collection + idempotency.

Chạy:
    python test_embed_owner.py

Không phụ thuộc vào các phần khác (cleaning_rules, expectations, freshness).
Tự tạo dữ liệu mẫu cleaned để test embed trực tiếp.
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

# --- Dữ liệu mẫu giả lập cleaned CSV (không cần chạy pipeline) ---
SAMPLE_CLEANED = [
    {
        "chunk_id": "test_refund_1_abc123",
        "doc_id": "policy_refund_v4",
        "chunk_text": "Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng.",
        "effective_date": "2026-02-01",
        "exported_at": "2026-04-10T08:00:00",
    },
    {
        "chunk_id": "test_sla_2_def456",
        "doc_id": "sla_p1_2026",
        "chunk_text": "Ticket P1 có SLA phản hồi ban đầu 15 phút và resolution trong 4 giờ.",
        "effective_date": "2026-02-01",
        "exported_at": "2026-04-10T08:00:00",
    },
    {
        "chunk_id": "test_faq_3_ghi789",
        "doc_id": "it_helpdesk_faq",
        "chunk_text": "Tài khoản bị khóa sau 5 lần đăng nhập sai liên tiếp.",
        "effective_date": "2026-02-01",
        "exported_at": "2026-04-10T08:00:00",
    },
]


def write_test_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_env_variables():
    """Test 1: Kiểm tra biến môi trường cần thiết đã được load."""
    print("=" * 60)
    print("TEST 1: Kiểm tra biến môi trường")
    print("=" * 60)

    required = {
        "SHOPAIKEY_API_KEY": "API key cho ShopAIKey",
        "CHROMA_DB_PATH": "Đường dẫn ChromaDB",
        "CHROMA_COLLECTION": "Tên collection",
        "OPENAI_EMBEDDING_MODEL": "Model embedding",
    }
    all_ok = True
    for key, desc in required.items():
        val = os.environ.get(key, "").strip()
        status = "✓" if val else "✗ THIẾU"
        if not val:
            all_ok = False
        # Mask API key
        display = val[:8] + "..." if key.endswith("_KEY") and val else val
        print(f"  {status} {key} = {display or '(trống)'} — {desc}")

    print(f"\n  → {'PASS' if all_ok else 'FAIL'}: Biến môi trường\n")
    return all_ok


def test_embedding_function():
    """Test 2: Kiểm tra tạo embedding function thành công + gọi API embed 1 câu."""
    print("=" * 60)
    print("TEST 2: Tạo embedding function + gọi API embed")
    print("=" * 60)

    from embedding_helper import get_embedding_function

    emb = get_embedding_function()
    print(f"  ✓ Embedding function: {type(emb).__name__}")
    print(f"  ✓ name() = {emb.name()}")

    # Thử embed 1 câu
    result = emb(["Đây là câu test embedding"])
    assert len(result) == 1, f"Expected 1 embedding, got {len(result)}"
    dim = len(result[0])
    print(f"  ✓ Embed 1 câu thành công — dimension={dim}")
    print(f"\n  → PASS: Embedding function hoạt động\n")
    return True


def test_chroma_collection():
    """Test 3: Kiểm tra tạo/get collection Chroma."""
    print("=" * 60)
    print("TEST 3: Tạo Chroma collection")
    print("=" * 60)

    from embedding_helper import get_chroma_client, get_collection_name, get_embedding_function

    client = get_chroma_client()
    collection_name = get_collection_name()
    emb = get_embedding_function()

    col = client.get_or_create_collection(name=collection_name, embedding_function=emb)
    print(f"  ✓ Collection '{collection_name}' created/got")
    print(f"  ✓ Current count: {col.count()}")
    print(f"\n  → PASS: Chroma collection\n")
    return True


def test_idempotent_upsert():
    """Test 4: Kiểm tra upsert idempotent — chạy 2 lần, count không đổi."""
    print("=" * 60)
    print("TEST 4: Idempotent upsert (chạy 2 lần)")
    print("=" * 60)

    from embedding_helper import get_chroma_client, get_collection_name, get_embedding_function

    # Dùng collection test riêng để không ảnh hưởng data chính
    test_col_name = "test_embed_owner_temp"
    client = get_chroma_client()
    emb = get_embedding_function()

    # Xóa collection test cũ nếu có
    try:
        client.delete_collection(test_col_name)
    except Exception:
        pass

    col = client.get_or_create_collection(name=test_col_name, embedding_function=emb)

    ids = [r["chunk_id"] for r in SAMPLE_CLEANED]
    documents = [r["chunk_text"] for r in SAMPLE_CLEANED]
    metadatas = [{"doc_id": r["doc_id"], "effective_date": r["effective_date"], "run_id": "test-run-1"} for r in SAMPLE_CLEANED]

    # Upsert lần 1
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    count_1 = col.count()
    print(f"  ✓ Upsert lần 1: count={count_1}")

    # Upsert lần 2 (cùng data)
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    count_2 = col.count()
    print(f"  ✓ Upsert lần 2: count={count_2}")

    assert count_1 == count_2 == len(SAMPLE_CLEANED), (
        f"Idempotency FAIL: expected {len(SAMPLE_CLEANED)}, got {count_1} then {count_2}"
    )
    print(f"  ✓ Count ổn định: {count_1} == {count_2} == {len(SAMPLE_CLEANED)}")

    # Cleanup
    client.delete_collection(test_col_name)
    print(f"  ✓ Cleanup: đã xóa collection test '{test_col_name}'")
    print(f"\n  → PASS: Idempotent upsert\n")
    return True


def test_prune_stale_ids():
    """Test 5: Kiểm tra prune id cũ khi cleaned thay đổi."""
    print("=" * 60)
    print("TEST 5: Prune stale IDs")
    print("=" * 60)

    from embedding_helper import get_chroma_client, get_embedding_function

    test_col_name = "test_prune_temp"
    client = get_chroma_client()
    emb = get_embedding_function()

    try:
        client.delete_collection(test_col_name)
    except Exception:
        pass

    col = client.get_or_create_collection(name=test_col_name, embedding_function=emb)

    # Upsert 3 records
    all_ids = [r["chunk_id"] for r in SAMPLE_CLEANED]
    all_docs = [r["chunk_text"] for r in SAMPLE_CLEANED]
    all_metas = [{"doc_id": r["doc_id"]} for r in SAMPLE_CLEANED]

    col.upsert(ids=all_ids, documents=all_docs, metadatas=all_metas)
    print(f"  ✓ Ban đầu: count={col.count()} (3 records)")

    # Giả lập cleaned mới chỉ còn 2 records (bỏ record cuối)
    new_ids = all_ids[:2]
    new_docs = all_docs[:2]
    new_metas = all_metas[:2]

    # Prune logic (giống etl_pipeline.py)
    prev = col.get(include=[])
    prev_ids = set(prev.get("ids") or [])
    drop = sorted(prev_ids - set(new_ids))
    if drop:
        col.delete(ids=drop)
        print(f"  ✓ Prune: xóa {len(drop)} id cũ → {drop}")

    col.upsert(ids=new_ids, documents=new_docs, metadatas=new_metas)
    final_count = col.count()
    print(f"  ✓ Sau prune + upsert: count={final_count}")

    assert final_count == 2, f"Expected 2, got {final_count}"

    # Cleanup
    client.delete_collection(test_col_name)
    print(f"  ✓ Cleanup: đã xóa collection test")
    print(f"\n  → PASS: Prune stale IDs\n")
    return True


def test_query_retrieval():
    """Test 6: Kiểm tra query retrieval trả về kết quả đúng."""
    print("=" * 60)
    print("TEST 6: Query retrieval")
    print("=" * 60)

    from embedding_helper import get_chroma_client, get_embedding_function

    test_col_name = "test_query_temp"
    client = get_chroma_client()
    emb = get_embedding_function()

    try:
        client.delete_collection(test_col_name)
    except Exception:
        pass

    col = client.get_or_create_collection(name=test_col_name, embedding_function=emb)

    ids = [r["chunk_id"] for r in SAMPLE_CLEANED]
    documents = [r["chunk_text"] for r in SAMPLE_CLEANED]
    metadatas = [{"doc_id": r["doc_id"]} for r in SAMPLE_CLEANED]

    col.upsert(ids=ids, documents=documents, metadatas=metadatas)

    # Query
    res = col.query(query_texts=["Bao nhiêu ngày để yêu cầu hoàn tiền?"], n_results=1)
    top_doc = (res.get("metadatas") or [[]])[0][0].get("doc_id", "")
    top_text = (res.get("documents") or [[]])[0][0]

    print(f"  ✓ Query: 'hoàn tiền'")
    print(f"    top1_doc_id = {top_doc}")
    print(f"    top1_text   = {top_text[:80]}...")
    assert "7 ngày" in top_text, f"Expected '7 ngày' in result"
    print(f"  ✓ Kết quả chứa '7 ngày' — đúng!")

    # Cleanup
    client.delete_collection(test_col_name)
    print(f"\n  → PASS: Query retrieval\n")
    return True


def main() -> int:
    print("\n" + "=" * 60)
    print("  TEST EMBED OWNER — Chroma Collection + Idempotency")
    print("=" * 60 + "\n")

    tests = [
        ("Env variables", test_env_variables),
        ("Embedding function", test_embedding_function),
        ("Chroma collection", test_chroma_collection),
        ("Idempotent upsert", test_idempotent_upsert),
        ("Prune stale IDs", test_prune_stale_ids),
        ("Query retrieval", test_query_retrieval),
    ]

    results = []
    for name, fn in tests:
        try:
            ok = fn()
            results.append((name, ok))
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}\n")
            results.append((name, False))

    print("=" * 60)
    print("  KẾT QUẢ TỔNG HỢP")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = "PASS ✓" if ok else "FAIL ✗"
        if not ok:
            all_pass = False
        print(f"  {status}  {name}")

    print(f"\n  {'ALL TESTS PASSED ✓' if all_pass else 'SOME TESTS FAILED ✗'}")
    print("=" * 60 + "\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
