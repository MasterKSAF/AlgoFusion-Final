from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_units import VALID_INVOICE_UNITS, normalize_invoice_unit_v2
from src.modules.runtime_numbers import (
    coerce_number as _coerce_number,
    extract_first_numeric_token as _extract_first_numeric_token,
)
from src.modules.runtime_text_quality import _clean_inline_text


def looks_like_percent_text(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if re.search(r"\b\d{1,2}(?:[.,]\d{1,2})?\s*%", cleaned):
        return True
    compact = re.sub(r"\s+", "", cleaned)
    return bool(re.fullmatch(r"(?:0|10|20)(?:[1Il|!.\u2026]{1,4})", compact))


def looks_like_money_text(text: Any) -> bool:
    return _extract_first_numeric_token(text, allow_integer=False) is not None


def looks_like_integer_text(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?", cleaned))


def invoice_barcode_cell_idx(cells: list[str]) -> int | None:
    for idx, text in enumerate(cells):
        cleaned = _clean_inline_text(text) or ""
        if re.fullmatch(r"\d{8,14}", cleaned):
            return idx
    for idx, text in enumerate(cells):
        if re.search(r"\d{8,14}", text or ""):
            return idx
    return None


def split_invoice_qty_unit(text: Any) -> tuple[int | float | None, str | None]:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None, None
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s+(.+?)\s*$", cleaned)
    if not match:
        return _coerce_number(_extract_first_numeric_token(cleaned)), normalize_invoice_unit_v2(cleaned)
    return _coerce_number(_extract_first_numeric_token(match.group(1))), normalize_invoice_unit_v2(match.group(2))


def looks_like_invoice_qty_unit_cell(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s+(.+?)\s*$", cleaned)
    if not match:
        return False
    qty = _coerce_number(_extract_first_numeric_token(match.group(1)))
    unit = normalize_invoice_unit_v2(match.group(2))
    if qty is None or unit is None:
        return False
    unit_clean = _clean_inline_text(match.group(2)) or ""
    if len(unit_clean) > 12 or re.search(r"\d", unit_clean):
        return False
    return unit in VALID_INVOICE_UNITS
