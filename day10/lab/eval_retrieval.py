#!/usr/bin/env python3
"""
Đánh giá retrieval đơn giản — before/after khi pipeline đổi dữ liệu embed.

Không bắt buộc LLM: chỉ kiểm tra top-k chunk có chứa keyword kỳ vọng hay không
(tiếp nối tinh thần Day 08/09 nhưng tập trung data layer).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def _log(msg: str) -> None:
    print(f"[eval] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        default=str(ROOT / "data" / "test_questions.json"),
        help="JSON danh sách câu hỏi golden (retrieval)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "eval" / "before_after_eval.csv"),
        help="CSV kết quả",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    t0 = time.perf_counter()
    _log(f"start top_k={args.top_k} questions={args.questions}")

    try:
        import chromadb  # noqa: F401
    except ImportError:
        print("Install: pip install chromadb", file=sys.stderr)
        return 1

    # TODO: Embed Owner — dùng chung embedding function từ helper
    t_imp = time.perf_counter()
    from embedding_helper import get_chroma_client, get_collection_name, get_embedding_function
    _log(f"imported embedding_helper in {time.perf_counter() - t_imp:.2f}s")

    qpath = Path(args.questions)
    if not qpath.is_file():
        print(f"questions not found: {qpath}", file=sys.stderr)
        return 1

    questions = json.loads(qpath.read_text(encoding="utf-8"))
    _log(f"loaded {len(questions)} questions")

    collection_name = get_collection_name()
    _log(f"collection_name={collection_name}")

    t_cli = time.perf_counter()
    client = get_chroma_client()
    _log(f"chroma client ready in {time.perf_counter() - t_cli:.2f}s")

    t_emb = time.perf_counter()
    emb = get_embedding_function()
    _log(f"embedding function built in {time.perf_counter() - t_emb:.2f}s (type={type(emb).__name__})")

    try:
        t_col = time.perf_counter()
        col = client.get_collection(name=collection_name, embedding_function=emb)
        _log(f"got collection in {time.perf_counter() - t_col:.2f}s count={col.count()}")
    except Exception as e:
        print(f"Collection error: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "question_id",
        "question",
        "top1_doc_id",
        "top1_preview",
        "contains_expected",
        "hits_forbidden",
        "top1_doc_expected",
        "top_k_used",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as fcsv:
        w = csv.DictWriter(fcsv, fieldnames=fieldnames)
        w.writeheader()
        t_loop = time.perf_counter()
        for i, q in enumerate(questions, start=1):
            text = q["question"]
            t_q = time.perf_counter()
            res = col.query(query_texts=[text], n_results=args.top_k)
            _log(f"q{i}/{len(questions)} query took {time.perf_counter() - t_q:.2f}s id={q.get('id', '')}")
            docs = (res.get("documents") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            top_doc = (metas[0] or {}).get("doc_id", "") if metas else ""
            preview = (docs[0] or "")[:180].replace("\n", " ") if docs else ""
            blob = " ".join(docs).lower()
            must_any = [x.lower() for x in q.get("must_contain_any", [])]
            forbidden = [x.lower() for x in q.get("must_not_contain", [])]
            ok_any = any(m in blob for m in must_any) if must_any else True
            bad_forb = any(m in blob for m in forbidden) if forbidden else False
            want_top1 = (q.get("expect_top1_doc_id") or "").strip()
            top1_expected = ""
            if want_top1:
                top1_expected = "yes" if top_doc == want_top1 else "no"
            w.writerow(
                {
                    "question_id": q.get("id", ""),
                    "question": text,
                    "top1_doc_id": top_doc,
                    "top1_preview": preview,
                    "contains_expected": "yes" if ok_any else "no",
                    "hits_forbidden": "yes" if bad_forb else "no",
                    "top1_doc_expected": top1_expected,
                    "top_k_used": args.top_k,
                }
            )

    _log(f"loop done in {time.perf_counter() - t_loop:.2f}s")
    _log(f"total elapsed {time.perf_counter() - t0:.2f}s")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
