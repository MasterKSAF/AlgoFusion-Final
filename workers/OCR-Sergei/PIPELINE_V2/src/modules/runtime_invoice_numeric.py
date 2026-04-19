from __future__ import annotations

from typing import Any

from src.modules.runtime_numbers import INVOICE_LINKED_NUMERIC_FIELDS, maybe_integral_quantity, numeric_close, positive_number, to_float_soft
from src.modules.runtime_numeric_common import (
    canonical_invoice_rate_text,
    has_numeric_review_marker,
    mark_linked_numeric_fields,
    rate_canonical_from_text,
    rate_value_from_canonical,
    set_clean_number,
)


def infer_invoice_rate_from_amounts(amount_excl: float | None, vat_amount: float | None, total: float | None) -> str | None:
    supports: list[str] = []
    if amount_excl is not None and amount_excl > 0:
        if vat_amount is not None:
            rate = canonical_invoice_rate_text((vat_amount / amount_excl) * 100.0)
            if rate:
                supports.append(rate)
        if total is not None:
            rate = canonical_invoice_rate_text(((total - amount_excl) / amount_excl) * 100.0)
            if rate:
                supports.append(rate)
    if not supports or len(set(supports)) != 1:
        return None
    return supports[0]


def invoice_no_discount_triplet(
    amount_incl: float | None,
    amount_excl: float | None,
    rate_value: float | None,
) -> tuple[float, float, float] | None:
    if amount_incl is None or amount_excl is None or rate_value is None:
        return None
    expected_total = round(float(amount_excl) * (1.0 + float(rate_value) / 100.0), 2)
    if not numeric_close(amount_incl, expected_total, abs_tol=0.08, rel_tol=0.02):
        return None
    vat_amount = round(float(amount_incl) - float(amount_excl), 2)
    return round(float(amount_excl), 2), vat_amount, round(float(amount_incl), 2)


def invoice_discount_total_triplet(
    amount_incl: float | None,
    discount: float | None,
    rate_value: float | None,
) -> tuple[float, float, float] | None:
    if amount_incl is None or discount is None or rate_value is None:
        return None
    candidate_total = round(float(amount_incl) - float(discount), 2)
    if candidate_total <= 0.0 or candidate_total > float(amount_incl) + 0.05:
        return None
    amount_excl = round(candidate_total / (1.0 + float(rate_value) / 100.0), 2)
    vat_amount = round(candidate_total - amount_excl, 2)
    return amount_excl, vat_amount, candidate_total


def finalize_invoice_numeric_row(row: dict[str, Any]) -> dict[str, Any]:
    if has_numeric_review_marker(row, INVOICE_LINKED_NUMERIC_FIELDS):
        mark_linked_numeric_fields(row, INVOICE_LINKED_NUMERIC_FIELDS)
        return row

    quantity = positive_number(row.get("quantity"))
    unit_price = positive_number(row.get("unit_price_incl_vat"))
    amount_incl = positive_number(row.get("amount_no_disc_incl_vat"), allow_zero=True)
    amount_excl = positive_number(row.get("amount_with_disc_excl_vat"), allow_zero=True)
    vat_amount = positive_number(row.get("vat_amount"), allow_zero=True)
    total = positive_number(row.get("total_with_disc_incl_vat"), allow_zero=True)
    rate_text = rate_canonical_from_text(row.get("vat_rate")) or infer_invoice_rate_from_amounts(amount_excl, vat_amount, total)
    rate_value = rate_value_from_canonical(rate_text)

    if amount_incl is None and quantity is not None and unit_price is not None:
        amount_incl = quantity * unit_price
    if unit_price is None and quantity is not None and amount_incl is not None and quantity > 0:
        unit_price = amount_incl / quantity
    if quantity is None and unit_price is not None and amount_incl is not None and unit_price > 0:
        quantity = maybe_integral_quantity(amount_incl / unit_price)

    discount = to_float_soft(row.get("disc_amount"))
    no_discount = discount is None or abs(discount) <= 0.005
    no_discount_triplet = invoice_no_discount_triplet(amount_incl, amount_excl, rate_value)
    no_discount_effective = no_discount or no_discount_triplet is not None

    if rate_text:
        row["vat_rate"] = rate_text
    if rate_value is not None:
        if amount_excl is None and no_discount and amount_incl is not None:
            amount_excl = round(amount_incl / (1.0 + rate_value / 100.0), 2)
        if vat_amount is None and amount_excl is not None:
            vat_amount = round(amount_excl * rate_value / 100.0, 2)
        if total is None and amount_excl is not None and vat_amount is not None:
            total = amount_excl + vat_amount
        if amount_excl is None and total is not None:
            amount_excl = round(total / (1.0 + rate_value / 100.0), 2)
        if vat_amount is None and amount_excl is not None and total is not None:
            vat_amount = total - amount_excl

    top_ready = all(value is not None for value in (quantity, unit_price, amount_incl))
    top_candidates = [amount_incl, amount_excl, total]
    top_ok = top_ready and any(numeric_close(quantity * unit_price, candidate) for candidate in top_candidates if candidate is not None)
    lower_ready = all(value is not None for value in (amount_excl, rate_value, vat_amount, total))
    lower_ok = False
    if lower_ready:
        vat_expected = round(amount_excl * rate_value / 100.0, 2)
        lower_ok = numeric_close(vat_amount, vat_expected, abs_tol=0.03, rel_tol=0.02) and numeric_close(
            total,
            amount_excl + vat_amount,
        )

    amount_relation_ok = True
    if lower_ready and amount_incl is not None:
        if no_discount_effective:
            amount_relation_ok = numeric_close(amount_incl, total) or numeric_close(amount_incl, amount_excl)
        else:
            amount_relation_ok = float(amount_incl) + 0.05 >= float(total)

    if not lower_ok and top_ok and rate_value is not None and amount_incl is not None and no_discount_triplet is not None:
        amount_excl, vat_amount, total = no_discount_triplet
        lower_ok = True
        amount_relation_ok = True
        discount = None
        no_discount_effective = True
        row["disc_amount"] = None
    elif (
        lower_ok
        and top_ok
        and not amount_relation_ok
        and no_discount_effective
        and rate_value is not None
        and amount_incl is not None
        and (
            (amount_excl is not None and float(amount_excl) > float(amount_incl) + 0.05)
            or (total is not None and float(total) > float(amount_incl) + 0.05)
        )
    ):
        amount_excl = round(amount_incl / (1.0 + rate_value / 100.0), 2)
        vat_amount = round(amount_incl - amount_excl, 2)
        total = amount_incl
        lower_ok = True
        amount_relation_ok = True
        discount = None
        row["disc_amount"] = None
    elif not lower_ok and no_discount_effective and top_ok and rate_value is not None and amount_incl is not None:
        amount_excl = round(amount_incl / (1.0 + rate_value / 100.0), 2)
        vat_amount = round(amount_incl - amount_excl, 2)
        total = amount_incl
        vat_expected = round(amount_excl * rate_value / 100.0, 2)
        lower_ok = numeric_close(vat_amount, vat_expected, abs_tol=0.03, rel_tol=0.02) and numeric_close(
            total,
            amount_excl + vat_amount,
        )
        amount_relation_ok = True
    elif not lower_ok and top_ok and rate_value is not None and amount_incl is not None and discount is not None:
        discount_triplet = invoice_discount_total_triplet(amount_incl, discount, rate_value)
        candidate_total = round(float(amount_incl) - float(discount), 2)
        if discount_triplet is not None and (
            total is None
            or numeric_close(total, candidate_total, abs_tol=0.55, rel_tol=0.05)
            or not amount_relation_ok
        ):
            amount_excl, vat_amount, total = discount_triplet
            vat_expected = round(amount_excl * rate_value / 100.0, 2)
            lower_ok = numeric_close(vat_amount, vat_expected, abs_tol=0.03, rel_tol=0.02) and numeric_close(
                total,
                amount_excl + vat_amount,
            )
            amount_relation_ok = numeric_close(amount_incl, discount + total, abs_tol=0.08, rel_tol=0.02)

    if not (top_ok and lower_ok and rate_text and amount_relation_ok):
        mark_linked_numeric_fields(row, INVOICE_LINKED_NUMERIC_FIELDS)
        return row

    set_clean_number(row, "quantity", quantity)
    set_clean_number(row, "unit_price_incl_vat", unit_price)
    set_clean_number(row, "amount_no_disc_incl_vat", amount_incl)
    set_clean_number(row, "amount_with_disc_excl_vat", amount_excl)
    row["vat_rate"] = rate_text
    set_clean_number(row, "vat_amount", vat_amount)
    set_clean_number(row, "total_with_disc_incl_vat", total)
    return row
