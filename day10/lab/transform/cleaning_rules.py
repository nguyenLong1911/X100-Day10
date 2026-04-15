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

# --- BASELINE REGEX ---
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_REFUND_14D = re.compile(r"\b14\s*ngày\s*làm\s*việc\b", flags=re.IGNORECASE)
HR_MIN_EFFECTIVE_DATE = "2026-01-01"

# --- RULE MỚI (sinh viên thêm) ---
# Rule 4: fix_leave_10_to_12 — "10 ngày phép" là bản HR 2025 cũ, đúng là 12 ngày (2026).
_LEAVE_10D = re.compile(r"\b10\s*ngày\s*phép\b", flags=re.IGNORECASE)

# Rule 5: fix_sick_leave_stale — nghỉ ốm đúng là 10 ngày, các bản cũ ghi 5 hoặc 7 ngày.
_SICK_LEAVE_WRONG = re.compile(r"\b(5|7)\s*ngày\s*nghỉ\s*ốm\b", flags=re.IGNORECASE)

# Rule 6: fix_lockout_threshold_stale — ngưỡng khóa đúng là 5 lần, bản cũ ghi 3 hoặc 10 lần.
_LOCKOUT_WRONG = re.compile(r"\b(3|10)\s*lần\s*đăng\s*nhập\s*sai\b", flags=re.IGNORECASE)


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


# =============================================================================
# BASELINE HELPER FUNCTIONS
# =============================================================================


# =============================================================================
# RULE MỚI — HELPER FUNCTIONS (sinh viên thêm)
# =============================================================================

def _replace_leave_10_to_12(text: str) -> Tuple[str, bool]:
    """
    Rule 4: fix_leave_10_to_12 — sửa ngày phép năm sai 10 -> 12.

    Nguồn chuẩn: hr_leave_policy.txt mục 1.1 (effective 2026-01-01).
    Trả về (fixed_text, changed).
    """
    fixed, n = _LEAVE_10D.subn("12 ngày phép", text)
    return fixed, n > 0


def _replace_sick_leave_stale(text: str) -> Tuple[str, bool]:
    """
    Rule 5: fix_sick_leave_stale — sửa số ngày nghỉ ốm sai (5/7) -> 10.

    Nguồn chuẩn: hr_leave_policy.txt mục 1.2 (10 ngày/năm có trả lương).
    Trả về (fixed_text, changed).
    """
    fixed, n = _SICK_LEAVE_WRONG.subn("10 ngày nghỉ ốm", text)
    return fixed, n > 0


def _replace_lockout_threshold_stale(text: str) -> Tuple[str, bool]:
    """
    Rule 6: fix_lockout_threshold_stale — sửa ngưỡng khóa tài khoản sai (3/10) -> 5 lần.

    Nguồn chuẩn: it_helpdesk_faq.txt Section 1 (5 lần đăng nhập sai).
    Trả về (fixed_text, changed).
    """
    fixed, n = _LOCKOUT_WRONG.subn("5 lần đăng nhập sai", text)
    return fixed, n > 0


# =============================================================================
# BASELINE HELPER FUNCTIONS (tiếp theo)
# =============================================================================

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

    Rules chính bao gồm 6 rule:
    1) quarantine_hr_old: Quarantine bản HR cũ theo cutoff effective_date.
    2) fix_refund_14_to_7: Chuẩn hoá cửa sổ hoàn tiền 14 -> 7 ngày làm việc.
    3) dedupe: Quarantine bản duplicate theo (doc_id, normalized_chunk_text).
    4) fix_leave_10_to_12: Sửa ngày phép năm sai 10 -> 12 trong hr_leave_policy.
    5) fix_sick_leave_stale: Sửa số ngày nghỉ ốm sai (5/7) -> 10 trong hr_leave_policy.
    6) fix_lockout_threshold_stale: Sửa ngưỡng khoá tài khoản sai (3/10) -> 5 lần trong it_helpdesk_faq.

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

        # --- BASELINE FIX RULES ---
        fixed_text = text
        fixed_applied = False
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            # Rule 2: fix_refund_14_to_7
            fixed_text, fixed_applied = _replace_refund_14d_to_7d(fixed_text)
            if fixed_applied:
                fixed_text += " [cleaned: stale_refund_window]"

        # --- RULE MỚI (sinh viên thêm) ---
        # Rule 4: fix_leave_10_to_12
        leave_fixed = False
        if doc_id == "hr_leave_policy":
            fixed_text, leave_fixed = _replace_leave_10_to_12(fixed_text)
            if leave_fixed:
                fixed_text += " [cleaned: stale_leave_days]"

        # Rule 5: fix_sick_leave_stale
        sick_fixed = False
        if doc_id == "hr_leave_policy":
            fixed_text, sick_fixed = _replace_sick_leave_stale(fixed_text)
            if sick_fixed:
                fixed_text += " [cleaned: stale_sick_leave]"

        # Rule 6: fix_lockout_threshold_stale
        lockout_fixed = False
        if doc_id == "it_helpdesk_faq":
            fixed_text, lockout_fixed = _replace_lockout_threshold_stale(fixed_text)
            if lockout_fixed:
                fixed_text += " [cleaned: stale_lockout_threshold]"

        impacts = []
        if fixed_applied:
            impacts.append("refund_14_to_7_fixed+1")
        if leave_fixed:
            impacts.append("leave_10_to_12_fixed+1")
        if sick_fixed:
            impacts.append("sick_leave_stale_fixed+1")
        if lockout_fixed:
            impacts.append("lockout_threshold_fixed+1")

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
                "rule_fix_refund_14_to_7": fixed_applied,
                "rule_fix_leave_10_to_12": leave_fixed,
                "rule_fix_sick_leave_stale": sick_fixed,
                "rule_fix_lockout_threshold_stale": lockout_fixed,
                "metric_impact": "; ".join(impacts),
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
