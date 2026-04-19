from __future__ import annotations

import copy
from typing import Any

from src.modules.runtime_numeric_reconciliation import canonical_invoice_rate_text, parse_percent_number
from src.modules.runtime_numbers import coerce_number, to_float_soft
from src.modules.runtime_text_quality import _clean_inline_text


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


def repair_invoice_shifted_tail_item(item: dict[str, Any], page_rate: str | None = None) -> dict[str, Any]:
    if not isinstance(item, dict):
        return item

    out = copy.deepcopy(item)
    current_rate_text = _clean_inline_text(out.get("vat_rate"))
    current_rate_value = parse_percent_number(current_rate_text)
    current_rate_canonical = canonical_invoice_rate_text(current_rate_value)
    disc_amount_value = to_float_soft(out.get("disc_amount"))
    disc_rate_canonical = canonical_invoice_rate_text(disc_amount_value)
    total_value = to_float_soft(out.get("total_with_disc_incl_vat"))
    vat_amount_value = to_float_soft(out.get("vat_amount"))
    amount_incl_value = to_float_soft(out.get("amount_no_disc_incl_vat"))
    amount_excl_value = to_float_soft(out.get("amount_with_disc_excl_vat"))

    target_rate = current_rate_canonical or disc_rate_canonical or page_rate
    if target_rate is not None and current_rate_canonical != target_rate:
        out["vat_rate"] = target_rate
    suspicious_shift = (
        target_rate is not None
        and (current_rate_canonical is None or current_rate_canonical != target_rate)
        and total_value is None
        and vat_amount_value is None
    )
    if not suspicious_shift:
        return out

    inferred_total = None
    if current_rate_value is not None:
        if current_rate_value < 1.0:
            inferred_total = current_rate_value
        elif amount_incl_value is not None and current_rate_value >= amount_incl_value * 0.8:
            inferred_total = current_rate_value

    out["vat_rate"] = target_rate
    if disc_rate_canonical or (disc_amount_value is not None and disc_amount_value > 100):
        out["disc_amount"] = None

    if inferred_total is not None and _is_missing(out.get("total_with_disc_incl_vat")):
        out["total_with_disc_incl_vat"] = coerce_number(inferred_total)
        total_value = inferred_total

    target_rate_value = parse_percent_number(target_rate)
    if amount_excl_value is None and total_value is not None and target_rate_value is not None:
        amount_excl_value = round(total_value / (1.0 + target_rate_value / 100.0), 2)
        out["amount_with_disc_excl_vat"] = coerce_number(amount_excl_value)

    if vat_amount_value is None and amount_excl_value is not None and target_rate_value is not None:
        vat_amount_value = round(amount_excl_value * target_rate_value / 100.0, 2)
        out["vat_amount"] = coerce_number(vat_amount_value)

    if _is_missing(out.get("total_with_disc_incl_vat")) and amount_excl_value is not None and vat_amount_value is not None:
        out["total_with_disc_incl_vat"] = coerce_number(amount_excl_value + vat_amount_value)

    return out
