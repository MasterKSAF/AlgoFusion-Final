from __future__ import annotations

from typing import Any

from src.modules.runtime_numbers import WAYBILL_LINKED_NUMERIC_FIELDS, maybe_integral_quantity, numeric_close, positive_number, to_float_soft
from src.modules.runtime_numeric_common import (
    has_numeric_review_marker,
    mark_linked_numeric_fields,
    rate_canonical_from_text,
    rate_value_from_canonical,
    rescale_small_money_to_reference,
    set_clean_number,
    snap_percent_to_canonical,
)


def reconcile_waybill_item_vat_rate(item: dict[str, Any]) -> str | None:
    cost = to_float_soft(item.get("cost"))
    vat_amount = to_float_soft(item.get("vat_amount"))
    total = to_float_soft(item.get("cost_with_vat"))
    supports: list[int] = []

    if cost is not None and abs(cost) > 1e-6 and vat_amount is not None:
        supports.append(snap_percent_to_canonical((vat_amount / cost) * 100.0))
    if cost is not None and abs(cost) > 1e-6 and total is not None:
        supports.append(snap_percent_to_canonical(((total - cost) / cost) * 100.0))
    supports = [value for value in supports if value is not None]
    if len(supports) < 2:
        return None
    if len(set(supports)) != 1:
        return None
    return f"{supports[0]}%"


def finalize_waybill_numeric_row(row: dict[str, Any]) -> dict[str, Any]:
    if has_numeric_review_marker(row, WAYBILL_LINKED_NUMERIC_FIELDS):
        mark_linked_numeric_fields(row, WAYBILL_LINKED_NUMERIC_FIELDS)
        return row

    quantity = positive_number(row.get("quantity"))
    price = positive_number(row.get("price"))
    cost = positive_number(row.get("cost"), allow_zero=True)
    vat_amount = positive_number(row.get("vat_amount"), allow_zero=True)
    total = positive_number(row.get("cost_with_vat"), allow_zero=True)
    rate_text = rate_canonical_from_text(row.get("vat_rate")) or reconcile_waybill_item_vat_rate(row)
    rate_value = rate_value_from_canonical(rate_text)

    if total is not None and vat_amount is not None:
        cost = rescale_small_money_to_reference(cost, total - vat_amount)
    if quantity is not None and price is not None:
        cost = rescale_small_money_to_reference(cost, quantity * price)

    if cost is None and total is not None and vat_amount is not None:
        cost = total - vat_amount
    if cost is None and total is not None and rate_value is not None:
        cost = total / (1.0 + rate_value / 100.0)
    if cost is None and quantity is not None and price is not None:
        cost = quantity * price
    if quantity is None and cost is not None and price is not None and price > 0:
        quantity = maybe_integral_quantity(cost / price)
    if price is None and cost is not None and quantity is not None and quantity > 0:
        price = cost / quantity

    if rate_text:
        row["vat_rate"] = rate_text
    if rate_value is not None:
        if vat_amount is None and cost is not None:
            vat_amount = round(cost * rate_value / 100.0, 2)
        if total is None and cost is not None and vat_amount is not None:
            total = cost + vat_amount
        if vat_amount is None and cost is not None and total is not None:
            vat_amount = total - cost

    required_ready = all(value is not None for value in (quantity, price, cost, rate_value, vat_amount, total))
    if not required_ready:
        mark_linked_numeric_fields(row, WAYBILL_LINKED_NUMERIC_FIELDS)
        return row

    vat_expected = round(cost * rate_value / 100.0, 2)
    if not (
        numeric_close(cost, quantity * price)
        and numeric_close(vat_amount, vat_expected, abs_tol=0.03, rel_tol=0.02)
        and numeric_close(total, cost + vat_amount)
    ):
        mark_linked_numeric_fields(row, WAYBILL_LINKED_NUMERIC_FIELDS)
        return row

    set_clean_number(row, "quantity", quantity)
    set_clean_number(row, "price", price)
    set_clean_number(row, "cost", cost)
    row["vat_rate"] = rate_text
    set_clean_number(row, "vat_amount", vat_amount)
    set_clean_number(row, "cost_with_vat", total)
    return row
