from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_numbers import coerce_number, numeric_close
from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER, _clean_inline_text, _is_review_field_marker


def set_clean_number(row: dict[str, Any], field: str, value: float | None) -> None:
    row[field] = coerce_number(None if value is None else round(float(value), 2))


def mark_linked_numeric_fields(row: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        row[field] = REVIEW_FIELD_MARKER


def parse_percent_number(text: Any) -> float | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    match = re.search(r"(\d{1,3}(?:[.,]\d{1,2})?)", cleaned)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except Exception:
        return None


def canonical_invoice_rate_text(value: float | None) -> str | None:
    if value is None:
        return None
    for candidate in (0.0, 10.0, 20.0, 25.0):
        if abs(value - candidate) <= 0.75:
            return f"{int(candidate)}%"
    return None


def rate_canonical_from_text(value: Any) -> str | None:
    canonical = canonical_invoice_rate_text(parse_percent_number(value))
    if canonical:
        return canonical
    cleaned = _clean_inline_text(value) or ""
    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return None
    if set(digits) <= {"0"}:
        return "0%"
    if "20" in digits and len(digits) <= 8:
        return "20%"
    if "10" in digits and len(digits) <= 8:
        return "10%"
    return None


def rate_value_from_canonical(rate: str | None) -> float | None:
    if not rate:
        return None
    return parse_percent_number(rate)


def has_numeric_review_marker(row: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(_is_review_field_marker(row.get(field)) for field in fields)


def snap_percent_to_canonical(value: float | None, *, tol: float = 1.0) -> int | None:
    if value is None:
        return None
    for candidate in (0, 10, 20):
        if abs(value - candidate) <= tol:
            return candidate
    return None


def rescale_small_money_to_reference(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None:
        return value
    if abs(float(reference)) >= 1.0 or abs(float(value)) < 10.0:
        return value
    for scale in (100.0, 1000.0, 10000.0):
        candidate = float(value) / scale
        if numeric_close(candidate, reference, abs_tol=0.05, rel_tol=0.25):
            return round(candidate, 2)
    return value
