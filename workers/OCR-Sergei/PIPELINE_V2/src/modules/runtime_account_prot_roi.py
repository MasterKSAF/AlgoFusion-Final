from __future__ import annotations

import copy
from typing import Any

from src.modules.runtime_account_prot_detection import looks_like_account_prot_table_header
from src.modules.runtime_account_prot_rows import (
    group_regions_by_rows,
    make_row_region,
    merge_account_prot_item_row,
    normalize_account_prot_total_row,
    rewrite_account_prot_row_text_from_ocr,
    row_join_text,
    text_from_ocr_items_in_bbox,
)


def repair_account_prot_roi_payload(payload: dict[str, Any], ocr_items: list[dict[str, Any]] | None = None) -> bool:
    regions = payload.get("regions")
    if not isinstance(regions, list):
        return False

    rows = group_regions_by_rows(regions, kind="table_cell", tol=14)
    header_row_idx = None
    for idx, row in enumerate(rows):
        if looks_like_account_prot_table_header(row_join_text(row)):
            header_row_idx = idx
            break
    if header_row_idx is None or header_row_idx <= 0:
        return False

    promoted_rows = rows[:header_row_idx]
    promoted_ids = {region.get("id") for row in promoted_rows for region in row}
    if not promoted_ids:
        return False

    synthetic_rows = []
    for idx, row in enumerate(promoted_rows, 1):
        region = make_row_region(row, kind="header_form_roi", prefix="header_form_roi_auto", idx=idx)
        if region is not None:
            ocr_text = text_from_ocr_items_in_bbox(ocr_items, tuple(region["bbox"]))
            if ocr_text:
                region["text"] = ocr_text
            synthetic_rows.append(region)
    if not synthetic_rows:
        return False

    rebuilt_table_rows = rows[header_row_idx:]
    rebuilt_table_cells: list[dict[str, Any]] = []
    for idx, row in enumerate(rebuilt_table_rows):
        normalized_row = row
        if idx > 0:
            normalized_row = merge_account_prot_item_row(row)
            normalized_row = rewrite_account_prot_row_text_from_ocr(normalized_row, ocr_items=ocr_items)
        normalized_row = normalize_account_prot_total_row(normalized_row)
        rebuilt_table_cells.extend(copy.deepcopy(region) for region in normalized_row)

    rebuilt: list[dict[str, Any]] = []
    for region in regions:
        if region.get("kind") == "table_cell":
            continue
        rebuilt.append(region)

    rebuilt.extend(synthetic_rows)
    rebuilt.extend(rebuilt_table_cells)

    payload["regions"] = rebuilt
    return True
