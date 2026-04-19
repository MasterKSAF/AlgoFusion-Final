from __future__ import annotations

from typing import Any

from src.modules.runtime_invoice_finalize import (
    finalize_invoice_payload_text as _finalize_invoice_payload_text,
    invoice_unit_suspicious as _invoice_unit_suspicious,
    trim_invoice_note_noise as _trim_invoice_note_noise,
)
from src.modules.runtime_invoice_overlay_builders import (
    build_invoice_items_overlay as _build_invoice_items_overlay_impl,
    build_invoice_raw_direct_rows_overlay as _build_invoice_raw_direct_rows_overlay_impl,
)
from src.modules.runtime_invoice_row_detection import looks_like_invoice_raw_direct_row as _looks_like_invoice_raw_direct_row_impl
from src.modules.runtime_invoice_raw import (
    build_invoice_raw_fallback_from_lines as _build_invoice_raw_fallback_from_lines,
    looks_like_invoice_index_row as _looks_like_invoice_index_row,
    looks_like_invoice_table_header as _looks_like_invoice_table_header,
)
from src.modules.runtime_invoice_vat_inference import infer_invoice_page_vat_rate as _infer_invoice_page_vat_rate_impl
from src.modules.runtime_numeric_reconciliation import (
    canonical_invoice_rate_text as _canonical_invoice_rate_text,
    parse_percent_number as _parse_percent_number,
)
from src.modules.runtime_regions import (
    group_ocr_lines as _group_ocr_lines,
    group_regions_by_rows as _group_regions_by_rows,
    row_join_text as _row_join_text,
    row_texts as _row_texts,
    row_to_pipe_text as _row_to_pipe_text,
)
from src.modules.runtime_text_quality import _clean_inline_text
from src.modules.runtime_types import PageWorkItem


def _build_invoice_items_overlay(item: PageWorkItem) -> list[dict[str, Any]]:
    return _build_invoice_items_overlay_impl(item)


def _looks_like_invoice_raw_direct_row(text: str) -> bool:
    return _looks_like_invoice_raw_direct_row_impl(text)


def _build_invoice_raw_direct_rows_overlay(item: PageWorkItem) -> list[dict[str, Any]]:
    return _build_invoice_raw_direct_rows_overlay_impl(item)


def _infer_invoice_page_vat_rate(item: PageWorkItem) -> str | None:
    return _infer_invoice_page_vat_rate_impl(item)


def _build_invoice_raw_fallback(item: PageWorkItem) -> dict[str, Any] | None:
    if not item.ocr_items:
        return None

    rows = _group_ocr_lines(item.ocr_items, y_tol=12)
    lines = [_row_to_pipe_text(row) for row in rows if _row_to_pipe_text(row)]
    return _build_invoice_raw_fallback_from_lines(lines, page_role=item.page_role)


def _repair_invoice_roi_payload(payload: dict[str, Any]) -> bool:
    regions = payload.get("regions")
    if not isinstance(regions, list):
        return False

    rows = _group_regions_by_rows(regions, kind="table_cell", tol=12)
    header_row_idx = None
    for idx, row in enumerate(rows):
        if _looks_like_invoice_table_header(_row_join_text(row)):
            header_row_idx = idx
            break
    if header_row_idx is None:
        return False

    remove_ids: set[str] = set()
    for row in rows[header_row_idx + 1 : header_row_idx + 3]:
        if _looks_like_invoice_index_row(_row_texts(row)):
            for region in row:
                region_id = region.get("id")
                if region_id:
                    remove_ids.add(str(region_id))
        else:
            break

    if not remove_ids:
        return False

    payload["regions"] = [
        region
        for region in regions
        if not (region.get("kind") == "table_cell" and str(region.get("id")) in remove_ids)
    ]
    return True


build_invoice_items_overlay = _build_invoice_items_overlay
build_invoice_raw_direct_rows_overlay = _build_invoice_raw_direct_rows_overlay
build_invoice_raw_fallback = _build_invoice_raw_fallback
finalize_invoice_payload_text = _finalize_invoice_payload_text
infer_invoice_page_vat_rate = _infer_invoice_page_vat_rate
invoice_unit_suspicious = _invoice_unit_suspicious
looks_like_invoice_raw_direct_row = _looks_like_invoice_raw_direct_row
repair_invoice_roi_payload = _repair_invoice_roi_payload
trim_invoice_note_noise = _trim_invoice_note_noise
