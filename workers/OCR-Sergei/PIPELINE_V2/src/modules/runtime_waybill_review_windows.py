from __future__ import annotations

import re
from typing import Any

from shared.resources.text_lexicon import WAYBILL_NAME_STOPWORDS
from src.modules.runtime_regions import group_ocr_lines as _group_ocr_lines
from src.modules.runtime_text_quality import _clean_inline_text
from src.modules.runtime_types import PageWorkItem


def extract_waybill_barcode_from_name(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    match = re.search(r"(?<!\d)(\d{8,14})(?!\d)", cleaned)
    return match.group(1) if match else None


def waybill_significant_name_tokens(text: Any) -> list[str]:
    cleaned = _clean_inline_text(text) or ""
    tokens = re.findall(r"[A-Za-z\u0410-\u044f\u0401\u0451]{4,}", cleaned)
    out: list[str] = []
    for token in tokens:
        token_lc = token.casefold()
        if token_lc in WAYBILL_NAME_STOPWORDS:
            continue
        if token_lc not in out:
            out.append(token_lc)
    return out[:8]


def waybill_group_raw_line_texts(item: PageWorkItem) -> list[str]:
    if not item.ocr_items:
        return []
    rows = _group_ocr_lines(item.ocr_items, y_tol=10)
    return [_clean_inline_text(row.get("text")) or "" for row in rows if _clean_inline_text(row.get("text"))]


def waybill_find_review_row_index(line_texts: list[str], row: dict[str, Any]) -> int | None:
    barcode = extract_waybill_barcode_from_name(row.get("name"))
    target_idx = None
    if barcode:
        for idx, line in enumerate(line_texts):
            if barcode in line:
                target_idx = idx
                break
    if target_idx is None:
        tokens = waybill_significant_name_tokens(row.get("name"))
        best_idx = None
        best_score = 0
        for idx, line in enumerate(line_texts):
            lowered = (line or "").lower()
            score = sum(1 for token in tokens if token in lowered)
            if score > best_score:
                best_idx = idx
                best_score = score
        if best_idx is not None and best_score >= 2:
            target_idx = best_idx
    return target_idx


def waybill_iter_review_row_windows(line_texts: list[str], row: dict[str, Any]) -> list[list[str]]:
    target_idx = waybill_find_review_row_index(line_texts, row)
    if target_idx is None:
        return []

    windows: list[list[str]] = []
    spans = [(0, 0), (-1, 0), (0, 1), (-1, 1), (-2, 2)]
    for start_offset, end_offset in spans:
        start = max(0, target_idx + start_offset)
        end = min(len(line_texts), target_idx + end_offset + 1)
        window = [line for line in line_texts[start:end] if line]
        if window and window not in windows:
            windows.append(window)
    return windows
