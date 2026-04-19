from __future__ import annotations

from typing import Any

from src.modules.runtime_account_prot_detection import (
    count_account_prot_pattern_hits as _count_account_prot_pattern_hits_impl,
    looks_like_account_prot_table_header as _looks_like_account_prot_table_header_impl,
)
from src.modules.runtime_account_prot_roi import repair_account_prot_roi_payload as _repair_account_prot_roi_payload_impl
from src.modules.runtime_account_prot_rows import (
    group_regions_by_rows as _group_regions_by_rows_impl,
    make_row_region as _make_row_region_impl,
    merge_account_prot_item_row as _merge_account_prot_item_row_impl,
    normalize_account_prot_total_row as _normalize_account_prot_total_row_impl,
    rewrite_account_prot_row_text_from_ocr as _rewrite_account_prot_row_text_from_ocr_impl,
    row_join_text as _row_join_text_impl,
    row_texts as _row_texts_impl,
    text_from_ocr_items_in_bbox as _text_from_ocr_items_in_bbox_impl,
)
from src.modules.runtime_account_prot_tail_repair import repair_shifted_account_prot_item as _repair_shifted_account_prot_item_impl


def _count_pattern_hits(text: str, patterns: list[str]) -> int:
    return _count_account_prot_pattern_hits_impl(text, patterns)


def looks_like_account_prot_table_header(text: str) -> bool:
    return _looks_like_account_prot_table_header_impl(text)


def repair_shifted_account_prot_item(item: dict[str, Any]) -> dict[str, Any]:
    return _repair_shifted_account_prot_item_impl(item)


def _group_regions_by_rows(regions: list[dict[str, Any]], kind: str = "table_cell", tol: int = 14) -> list[list[dict[str, Any]]]:
    return _group_regions_by_rows_impl(regions, kind=kind, tol=tol)


def _row_texts(regions: list[dict[str, Any]]) -> list[str]:
    return _row_texts_impl(regions)


def _row_join_text(regions: list[dict[str, Any]]) -> str:
    return _row_join_text_impl(regions)


def make_row_region(row: list[dict[str, Any]], kind: str, prefix: str, idx: int) -> dict[str, Any] | None:
    return _make_row_region_impl(row, kind, prefix, idx)


def text_from_ocr_items_in_bbox(
    ocr_items: list[dict[str, Any]] | None,
    bbox: tuple[int, int, int, int],
    y_tol: int = 12,
) -> str | None:
    return _text_from_ocr_items_in_bbox_impl(ocr_items, bbox, y_tol=y_tol)


def merge_account_prot_item_row(row: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _merge_account_prot_item_row_impl(row)


def normalize_account_prot_total_row(row: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _normalize_account_prot_total_row_impl(row)


def rewrite_account_prot_row_text_from_ocr(
    row: list[dict[str, Any]],
    ocr_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return _rewrite_account_prot_row_text_from_ocr_impl(row, ocr_items=ocr_items)


def repair_account_prot_roi_payload(payload: dict[str, Any], ocr_items: list[dict[str, Any]] | None = None) -> bool:
    return _repair_account_prot_roi_payload_impl(payload, ocr_items=ocr_items)
