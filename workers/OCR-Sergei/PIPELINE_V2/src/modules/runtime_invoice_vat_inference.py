from __future__ import annotations

import re

from src.modules.runtime_numeric_reconciliation import (
    canonical_invoice_rate_text as _canonical_invoice_rate_text,
    parse_percent_number as _parse_percent_number,
)
from src.modules.runtime_regions import group_ocr_lines as _group_ocr_lines, load_roi_text_regions as _load_roi_text_regions
from src.modules.runtime_text_quality import _clean_inline_text
from src.modules.runtime_types import PageWorkItem


def infer_invoice_page_vat_rate(item: PageWorkItem) -> str | None:
    counts: dict[str, int] = {}
    regions = _load_roi_text_regions(item)
    for region in regions:
        if region.get("kind") != "table_cell":
            continue
        text = _clean_inline_text(region.get("text")) or ""
        for match in re.finditer(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%", text):
            rate = _canonical_invoice_rate_text(_parse_percent_number(match.group(1)))
            if rate:
                counts[rate] = counts.get(rate, 0) + 1
    if not counts and item.ocr_items:
        for row in _group_ocr_lines(item.ocr_items, y_tol=10):
            text = _clean_inline_text(row.get("text")) or ""
            for match in re.finditer(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*%", text):
                rate = _canonical_invoice_rate_text(_parse_percent_number(match.group(1)))
                if rate:
                    counts[rate] = counts.get(rate, 0) + 1
    if not counts:
        return None
    best_rate, best_count = max(counts.items(), key=lambda item: item[1])
    return best_rate if best_count >= 2 else None
