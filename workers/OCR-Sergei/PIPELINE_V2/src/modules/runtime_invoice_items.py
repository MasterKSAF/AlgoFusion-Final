from __future__ import annotations

from typing import Any

from src.modules.runtime_invoice_articles import (
    clean_invoice_description_value as _clean_invoice_description_value_impl,
    extract_invoice_article_candidate as _extract_invoice_article_candidate_impl,
    extract_invoice_article_token as _extract_invoice_article_token_impl,
    extract_invoice_barcode_cell_description as _extract_invoice_barcode_cell_description_impl,
    extract_invoice_lead_fields as _extract_invoice_lead_fields_impl,
    extract_invoice_lead_parts as _extract_invoice_lead_parts_impl,
    looks_like_invoice_article_cell as _looks_like_invoice_article_cell_impl,
    normalize_invoice_article_value as _normalize_invoice_article_value_impl,
)
from src.modules.runtime_invoice_cells import (
    invoice_barcode_cell_idx as _invoice_barcode_cell_idx_impl,
    looks_like_integer_text as _looks_like_integer_text_impl,
    looks_like_invoice_qty_unit_cell as _looks_like_invoice_qty_unit_cell_impl,
    looks_like_money_text as _looks_like_money_text_impl,
    looks_like_percent_text as _looks_like_percent_text_impl,
    split_invoice_qty_unit as _split_invoice_qty_unit_impl,
)
from src.modules.runtime_invoice_item_canonicalize import canonicalize_invoice_items as _canonicalize_invoice_items_impl
from src.modules.runtime_invoice_item_quality import invoice_item_suspicious as _invoice_item_suspicious_impl
from src.modules.runtime_invoice_region_row import parse_invoice_region_row as _parse_invoice_region_row_impl
from src.modules.runtime_invoice_units import (
    INV_UNIT_KG,
    INV_UNIT_L,
    INV_UNIT_ML,
    INV_UNIT_PACK,
    INV_UNIT_PCS,
    VALID_INVOICE_UNITS,
    looks_like_invoice_unit_cell as _looks_like_invoice_unit_cell_impl,
    normalize_invoice_unit_v2 as _normalize_invoice_unit_v2_impl,
)


def extract_invoice_article_candidate(text: Any, line_number: int | None = None) -> str | None:
    return _extract_invoice_article_candidate_impl(text, line_number)


def normalize_invoice_unit_v2(text: Any) -> str | None:
    return _normalize_invoice_unit_v2_impl(text)


def looks_like_invoice_unit_cell(text: Any) -> bool:
    return _looks_like_invoice_unit_cell_impl(text)


def invoice_barcode_cell_idx(cells: list[str]) -> int | None:
    return _invoice_barcode_cell_idx_impl(cells)


def extract_invoice_lead_parts(text: Any, fallback_line_number: int) -> tuple[int | None, str | None]:
    return _extract_invoice_lead_parts_impl(text, fallback_line_number)


def normalize_invoice_article_value(text: Any) -> str | None:
    return _normalize_invoice_article_value_impl(text)


def extract_invoice_article_token(text: Any) -> str | None:
    return _extract_invoice_article_token_impl(text)


def looks_like_invoice_article_cell(text: Any) -> bool:
    return _looks_like_invoice_article_cell_impl(text)


def extract_invoice_lead_fields(
    lead_cells: list[str],
    fallback_line_number: int,
) -> tuple[int | None, str | None, str | None]:
    return _extract_invoice_lead_fields_impl(lead_cells, fallback_line_number)


def clean_invoice_description_value(text: Any, article: str | None = None) -> str | None:
    return _clean_invoice_description_value_impl(text, article=article)


def extract_invoice_barcode_cell_description(text: Any, article: str | None = None) -> str | None:
    return _extract_invoice_barcode_cell_description_impl(text, article=article)


def canonicalize_invoice_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _canonicalize_invoice_items_impl(items)


_normalize_invoice_unit_v2 = normalize_invoice_unit_v2
_looks_like_invoice_unit_cell = looks_like_invoice_unit_cell
_invoice_barcode_cell_idx = invoice_barcode_cell_idx
_extract_invoice_lead_fields = extract_invoice_lead_fields
_clean_invoice_description_value = clean_invoice_description_value
_extract_invoice_barcode_cell_description = extract_invoice_barcode_cell_description
_VALID_INVOICE_UNITS_IMPL = VALID_INVOICE_UNITS


def _looks_like_percent_text(text: Any) -> bool:
    return _looks_like_percent_text_impl(text)


def _looks_like_money_text(text: Any) -> bool:
    return _looks_like_money_text_impl(text)


def _looks_like_integer_text(text: Any) -> bool:
    return _looks_like_integer_text_impl(text)


def _split_invoice_qty_unit(text: Any) -> tuple[int | float | None, str | None]:
    return _split_invoice_qty_unit_impl(text)


def _looks_like_invoice_qty_unit_cell(text: Any) -> bool:
    return _looks_like_invoice_qty_unit_cell_impl(text)


def _invoice_item_suspicious(item: dict[str, Any]) -> bool:
    return _invoice_item_suspicious_impl(item)


def _parse_invoice_region_row(texts: list[str], fallback_line_number: int) -> dict[str, Any] | None:
    return _parse_invoice_region_row_impl(texts, fallback_line_number)


looks_like_percent_text = _looks_like_percent_text
looks_like_money_text = _looks_like_money_text
looks_like_integer_text = _looks_like_integer_text
split_invoice_qty_unit = _split_invoice_qty_unit
looks_like_invoice_qty_unit_cell = _looks_like_invoice_qty_unit_cell
invoice_item_suspicious = _invoice_item_suspicious
parse_invoice_region_row = _parse_invoice_region_row
