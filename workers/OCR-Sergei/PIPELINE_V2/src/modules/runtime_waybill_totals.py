from __future__ import annotations

from typing import Any

from src.modules.runtime_numbers import to_float_soft
from src.modules.runtime_text_quality import REVIEW_FIELD_MARKER, _clean_inline_text


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(_is_missing(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_missing(item) for item in value.values())
    return False


def coerce_waybill_total(value: float | None) -> int | float | None:
    if value is None:
        return None
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 1e-6:
        return int(round(rounded))
    return rounded


def compute_waybill_totals_from_items(items: list[dict[str, Any]]) -> dict[str, int | float | None]:
    if not isinstance(items, list) or not items:
        return {}

    sums = {
        "quantity_total": 0.0,
        "cost_total": 0.0,
        "vat_total": 0.0,
        "cost_with_vat_total": 0.0,
    }
    seen_any = False
    for row in items:
        if not isinstance(row, dict):
            return {}
        values: dict[str, float] = {}
        for field, total_field in [
            ("quantity", "quantity_total"),
            ("cost", "cost_total"),
            ("vat_amount", "vat_total"),
            ("cost_with_vat", "cost_with_vat_total"),
        ]:
            raw_value = row.get(field)
            if str(_clean_inline_text(raw_value) or "").lower() == REVIEW_FIELD_MARKER:
                return {}
            parsed = to_float_soft(raw_value)
            if parsed is None:
                return {}
            values[total_field] = parsed
        seen_any = True
        for total_field, parsed in values.items():
            sums[total_field] += parsed

    if not seen_any:
        return {}
    return {field: coerce_waybill_total(value) for field, value in sums.items()}


def fill_waybill_totals_from_safe_sources(out: dict[str, Any]) -> None:
    totals = out.get("totals")
    if not isinstance(totals, dict):
        return

    cost_total = to_float_soft(totals.get("cost_total"))
    vat_total = to_float_soft(totals.get("vat_total"))
    total_with_vat = to_float_soft(totals.get("cost_with_vat_total"))

    if total_with_vat is None and cost_total is not None and vat_total is not None:
        totals["cost_with_vat_total"] = coerce_waybill_total(cost_total + vat_total)
        total_with_vat = to_float_soft(totals.get("cost_with_vat_total"))
    if cost_total is None and total_with_vat is not None and vat_total is not None:
        totals["cost_total"] = coerce_waybill_total(total_with_vat - vat_total)
    if vat_total is None and total_with_vat is not None and cost_total is not None:
        totals["vat_total"] = coerce_waybill_total(total_with_vat - cost_total)

    computed = compute_waybill_totals_from_items(out.get("items") or [])
    for field, value in computed.items():
        if _is_missing(totals.get(field)) and value is not None:
            totals[field] = value
