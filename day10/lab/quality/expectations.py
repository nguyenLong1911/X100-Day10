"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str
    metric_impact: str  # Đánh giá tác động đến metric nếu expectation này fail


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
            "Pipeline trả về dữ liệu rỗng; Recall = 0%"
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
            "Lỗi ghi dữ liệu vào Vector DB do thiếu định danh (ID)"
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
            "LLM có thể hallucinate chính sách hoàn tiền cũ, gây sai lệch thông tin CSKH"
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
            "Tăng số lượng chunk rác, làm giảm độ chính xác (Precision) của Semantic Search"
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
            "Tính năng Metadata Filtering theo ngày tháng sẽ bị crash hoặc trả về kết quả sai"
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
            "Nhân sự nhận được thông tin sai về ngày phép, ảnh hưởng đến độ tin cậy của hệ thống (Trust Score giảm)"
        )
    )

    # -------------------------------------------------------------------------
    # NEW EXPECTATIONS
    # -------------------------------------------------------------------------

    # E7: Các dòng phải có đủ các trường (keys) tối thiểu để embed
    required_keys = {"doc_id", "chunk_text"}
    missing_keys_rows = [
        r for r in cleaned_rows
        if not required_keys.issubset(r.keys())
    ]
    ok7 = len(missing_keys_rows) == 0
    results.append(
        ExpectationResult(
            "has_required_schema_keys",
            ok7,
            "halt",
            f"rows_missing_keys={len(missing_keys_rows)}",
            "Tiến trình Embedding/Lưu trữ downstream sẽ văng lỗi KeyError làm sập toàn bộ pipeline"
        )
    )

    # E8: Phát hiện lỗi encoding (Ký tự thay thế Unicode \uFFFD)
    bad_encoding = [
        r for r in cleaned_rows
        if "\ufffd" in (r.get("chunk_text") or "")
    ]
    ok8 = len(bad_encoding) == 0
    results.append(
        ExpectationResult(
            "no_unicode_replacement_chars",
            ok8,
            "halt",
            f"corrupted_rows={len(bad_encoding)}",
            "Chất lượng RAG bị phá hủy hoàn toàn do text đầu vào bị lỗi font/mã hóa không thể đọc được"
        )
    )

    # Kiểm tra điều kiện halt có kiểm soát
    halt = any(not r.passed and r.severity == "halt" for r in results)
    
    return results, halt