from __future__ import annotations

from typing import Any

from src.modules.runtime_numbers import coerce_number, to_float_soft


def summarize_invoice_item_totals(items: list[dict[str, Any]]) -> dict[str, Any]:
    qty_total = 0.0
    qty_seen = False
    subtotal = 0.0
    subtotal_seen = False
    vat_total = 0.0
    vat_seen = False
    total_sum = 0.0
    total_seen = False

    for row in items:
        qty = to_float_soft(row.get("quantity"))
        amount = to_float_soft(row.get("amount_with_disc_excl_vat"))
        vat = to_float_soft(row.get("vat_amount"))
        total = to_float_soft(row.get("total_with_disc_incl_vat"))
        if qty is not None:
            qty_total += qty
            qty_seen = True
        if amount is not None:
            subtotal += amount
            subtotal_seen = True
        if vat is not None:
            vat_total += vat
            vat_seen = True
        if total is not None:
            total_sum += total
            total_seen = True

    totals: dict[str, Any] = {}
    if qty_seen:
        totals["total_quantity"] = coerce_number(qty_total)
    if subtotal_seen:
        totals["subtotal_with_disc_excl_vat"] = coerce_number(subtotal)
    if vat_seen:
        totals["vat_amount"] = coerce_number(vat_total)
    if total_seen:
        totals["total_with_disc_incl_vat"] = coerce_number(total_sum)
    return totals
