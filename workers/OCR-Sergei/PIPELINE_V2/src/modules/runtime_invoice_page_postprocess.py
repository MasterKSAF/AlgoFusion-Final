from __future__ import annotations

from typing import Any, Callable

from src.modules.runtime_invoice_items import (
    canonicalize_invoice_items as _canonicalize_invoice_items,
    invoice_item_suspicious as _invoice_item_suspicious,
    normalize_invoice_unit_v2 as _normalize_invoice_unit_v2,
)
from src.modules.runtime_invoice_postprocess import (
    build_invoice_items_overlay as _build_invoice_items_overlay,
    build_invoice_raw_direct_rows_overlay as _build_invoice_raw_direct_rows_overlay,
    build_invoice_raw_fallback as _build_invoice_raw_fallback,
    infer_invoice_page_vat_rate as _infer_invoice_page_vat_rate,
    invoice_unit_suspicious as _invoice_unit_suspicious,
    trim_invoice_note_noise as _trim_invoice_note_noise,
)
from src.modules.runtime_invoice_raw import repair_invoice_shifted_tail_item as _repair_invoice_shifted_tail_item
from src.modules.runtime_types import PageWorkItem


def postprocess_invoice_prediction(
    item: PageWorkItem,
    out: dict[str, Any],
    *,
    is_missing: Callable[[Any], bool],
    deep_fill: Callable[[Any, Any], Any],
    review_marker_or_none: Callable[[Any], Any],
) -> dict[str, Any]:
    needs_raw_fallback = (
        is_missing(out.get("invoice_number"))
        and is_missing(out.get("invoice_date"))
        and is_missing((out.get("supplier") or {}).get("name"))
        and not (out.get("items") or [])
    ) or (
        item.page_role in {"last", "single"}
        and is_missing((out.get("signatory") or {}).get("name"))
        and is_missing(out.get("note"))
    )
    if needs_raw_fallback:
        raw_fallback = _build_invoice_raw_fallback(item)
        if raw_fallback:
            out = deep_fill(out, raw_fallback)

    current_items = [row for row in (out.get("items") or []) if isinstance(row, dict)]
    if item.page_role in {"first", "single", "middle", "last"}:
        overlay_items = _build_invoice_items_overlay(item)
        raw_direct_items = _build_invoice_raw_direct_rows_overlay(item)
    else:
        overlay_items = []
        raw_direct_items = []

    current_suspicious = not current_items or any(_invoice_item_suspicious(row) for row in current_items)
    overlay_usable = len(overlay_items) >= max(1, len(current_items) // 2) and not any(
        _invoice_item_suspicious(row) for row in overlay_items
    )
    raw_direct_usable = len(raw_direct_items) >= max(1, len(current_items) // 2) and not any(
        _invoice_item_suspicious(row) for row in raw_direct_items
    )

    if current_suspicious and overlay_usable and (not raw_direct_usable or len(overlay_items) >= len(raw_direct_items)):
        out["items"] = overlay_items
    elif current_suspicious and raw_direct_usable:
        out["items"] = raw_direct_items
    elif item.page_role in {"middle", "last"} and overlay_items:
        out["items"] = overlay_items
    elif current_suspicious and overlay_usable:
        out["items"] = overlay_items
    elif not current_items and overlay_items:
        out["items"] = overlay_items

    if isinstance(out.get("items"), list):
        page_rate = _infer_invoice_page_vat_rate(item)
        repaired_rows = [_repair_invoice_shifted_tail_item(row, page_rate=page_rate) for row in out["items"]]
        out["items"] = _canonicalize_invoice_items(repaired_rows)
        for row in out["items"]:
            if not isinstance(row, dict):
                continue
            normalized_unit = _normalize_invoice_unit_v2(row.get("unit"))
            if normalized_unit and not _invoice_unit_suspicious(normalized_unit):
                row["unit"] = normalized_unit
            elif _invoice_unit_suspicious(row.get("unit")) or _invoice_unit_suspicious(normalized_unit):
                row["unit"] = review_marker_or_none(row.get("unit"))

    out["note"] = _trim_invoice_note_noise(out.get("note"))
    return out
