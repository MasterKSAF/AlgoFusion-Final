from __future__ import annotations

from typing import Any

from src.modules.runtime_invoice_raw_blocks import collect_invoice_raw_item_blocks as _collect_invoice_raw_item_blocks_impl
from src.modules.runtime_invoice_raw_detection import (
    count_pattern_hits as _count_pattern_hits_impl,
    looks_like_invoice_index_row as _looks_like_invoice_index_row_impl,
    looks_like_invoice_table_header as _looks_like_invoice_table_header_impl,
    normalize_invoice_unit as _normalize_invoice_unit_impl,
)
from src.modules.runtime_invoice_raw_fallback import build_invoice_raw_fallback_from_lines as _build_invoice_raw_fallback_from_lines_impl
from src.modules.runtime_invoice_raw_item_block import parse_invoice_raw_item_block as _parse_invoice_raw_item_block_impl
from src.modules.runtime_invoice_tail_repair import repair_invoice_shifted_tail_item as _repair_invoice_shifted_tail_item_impl


def _count_pattern_hits(text: Any, patterns: list[str]) -> int:
    return _count_pattern_hits_impl(text, patterns)


def normalize_invoice_unit(text: Any) -> str | None:
    return _normalize_invoice_unit_impl(text)


def looks_like_invoice_table_header(text: str) -> bool:
    return _looks_like_invoice_table_header_impl(text)


def looks_like_invoice_index_row(texts: list[str]) -> bool:
    return _looks_like_invoice_index_row_impl(texts)


def repair_invoice_shifted_tail_item(item: dict[str, Any], page_rate: str | None = None) -> dict[str, Any]:
    return _repair_invoice_shifted_tail_item_impl(item, page_rate)


def collect_invoice_raw_item_blocks(lines: list[str]) -> list[list[str]]:
    return _collect_invoice_raw_item_blocks_impl(lines)


def parse_invoice_raw_item_block(block_lines: list[str], line_number: int) -> dict[str, Any] | None:
    return _parse_invoice_raw_item_block_impl(block_lines, line_number)


def build_invoice_raw_fallback_from_lines(lines: list[str], page_role: str | None = None) -> dict[str, Any] | None:
    return _build_invoice_raw_fallback_from_lines_impl(lines, page_role)
