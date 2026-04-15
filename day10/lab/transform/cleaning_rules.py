"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_REFUND_14D = re.compile(r"\b14\s*ngày\s*làm\s*việc\b", flags=re.IGNORECASE)
HR_MIN_EFFECTIVE_DATE = "2026-01-01"


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _replace_refund_14d_to_7d(text: str) -> Tuple[str, bool]:
    """
    Rule: fix stale refund window 14 -> 7.

    Trả về (fixed_text, changed).
    """
    fixed, changed_count = _REFUND_14D.subn("7 ngày làm việc", text)
    return fixed, changed_count > 0


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Rules chính (bao gồm 3 rule bạn cần mở rộng trong Sprint 2):
    1) quarantine_hr_old: Quarantine bản HR cũ theo cutoff effective_date.
    2) fix_refund_14_to_7: Chuẩn hoá cửa sổ hoàn tiền 14 -> 7 ngày làm việc.
    3) dedupe: Quarantine bản duplicate theo (doc_id, normalized_chunk_text).

    Mỗi rule mới đều ghi metric_impact để nhóm dùng làm bằng chứng non-trivial trong report.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text_by_doc: set[Tuple[str, str]] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append(
                {
                    **raw,
                    "reason": "unknown_doc_id",
                    "metric_impact": "quarantine_records+1",
                }
            )
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append(
                {
                    **raw,
                    "reason": "missing_effective_date",
                    "metric_impact": "quarantine_records+1",
                }
            )
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append(
                {
                    **raw,
                    "reason": eff_err,
                    "effective_date_raw": eff_raw,
                    "metric_impact": "quarantine_records+1",
                }
            )
            continue

        # Rule 1: quarantine_hr_old
        if doc_id == "hr_leave_policy" and eff_norm < HR_MIN_EFFECTIVE_DATE:
            quarantine.append(
                {
                    **raw,
                    "reason": "quarantine_hr_old",
                    "effective_date_normalized": eff_norm,
                    "metric_impact": "quarantine_records+1; stale_hr_rows_removed+1",
                }
            )
            continue

        if not text:
            quarantine.append(
                {
                    **raw,
                    "reason": "missing_chunk_text",
                    "metric_impact": "quarantine_records+1",
                }
            )
            continue

        # Rule 3: dedupe
        key = (doc_id, _norm_text(text))
        if key in seen_text_by_doc:
            quarantine.append(
                {
                    **raw,
                    "reason": "dedupe_duplicate_chunk_text",
                    "metric_impact": "quarantine_records+1; duplicate_rows_removed+1",
                }
            )
            continue
        seen_text_by_doc.add(key)

        fixed_text = text
        fixed_applied = False
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            # Rule 2: fix_refund_14_to_7
            fixed_text, fixed_applied = _replace_refund_14d_to_7d(fixed_text)
            if fixed_applied:
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
                "rule_fix_refund_14_to_7": fixed_applied,
                "metric_impact": "refund_14_to_7_fixed+1" if fixed_applied else "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
