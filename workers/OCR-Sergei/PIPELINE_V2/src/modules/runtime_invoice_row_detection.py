from __future__ import annotations

import re

from src.modules.runtime_invoice_items import (
    invoice_barcode_cell_idx as _invoice_barcode_cell_idx,
    looks_like_integer_text as _looks_like_integer_text,
    looks_like_invoice_qty_unit_cell as _looks_like_invoice_qty_unit_cell,
    looks_like_money_text as _looks_like_money_text,
    looks_like_percent_text as _looks_like_percent_text,
    normalize_invoice_unit_v2 as _normalize_invoice_unit_v2,
    parse_invoice_region_row as _parse_invoice_region_row,
)
from src.modules.runtime_text_quality import _clean_inline_text


def looks_like_invoice_raw_direct_row(text: str) -> bool:
    cells = [_clean_inline_text(part) for part in re.split(r"\s*\|\s*", text) if _clean_inline_text(part)]
    if len(cells) < 8:
        return False
    if _parse_invoice_region_row(cells, fallback_line_number=1) is not None:
        return True
    percent_idx = next((idx for idx, cell in enumerate(cells) if _looks_like_percent_text(cell)), None)
    qty_split = any(
        _looks_like_integer_text(cells[idx]) and _normalize_invoice_unit_v2(cells[idx + 1]) is not None
        for idx in range(max(0, len(cells) - 1))
    )
    if (
        percent_idx is not None
        and sum(1 for cell in cells if _looks_like_money_text(cell)) >= 3
        and (_looks_like_integer_text(cells[0]) or bool(re.fullmatch(r"\d{1,3}", cells[0] or "")))
        and bool(_clean_inline_text(cells[1]))
        and bool(_clean_inline_text(cells[2]))
        and (qty_split or any(_looks_like_invoice_qty_unit_cell(cell) for cell in cells))
    ):
        return True
    return (
        _invoice_barcode_cell_idx(cells) is not None
        and any(_looks_like_invoice_qty_unit_cell(cell) for cell in cells)
        and any(_looks_like_percent_text(cell) for cell in cells)
        and sum(1 for cell in cells if _looks_like_money_text(cell)) >= 3
    )
