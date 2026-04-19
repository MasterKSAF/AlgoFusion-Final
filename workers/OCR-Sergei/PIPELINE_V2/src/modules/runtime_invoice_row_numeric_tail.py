from __future__ import annotations

from typing import Any

from src.modules.runtime_numbers import coerce_number, extract_first_numeric_token
from src.modules.runtime_text_quality import _clean_inline_text


def build_invoice_numeric_tail_row(
    *,
    line_number: int | None,
    article: str | None,
    description: str | None,
    barcode: str | None,
    quantity: int | float | None,
    unit: str | None,
    before_rate: list[str],
    vat_rate_text: Any,
    after_rate: list[str],
) -> dict[str, Any] | None:
    if quantity is None or not unit or len(before_rate) < 2 or len(after_rate) < 2:
        return None

    price = coerce_number(extract_first_numeric_token(before_rate[0], allow_integer=False))
    amount_no_disc = coerce_number(extract_first_numeric_token(before_rate[1], allow_integer=False))
    disc_amount = coerce_number(extract_first_numeric_token(before_rate[2], allow_integer=False)) if len(before_rate) >= 4 else None
    amount_excl_idx = 3 if len(before_rate) >= 4 else 2 if len(before_rate) >= 3 else None
    amount_excl = (
        coerce_number(extract_first_numeric_token(before_rate[amount_excl_idx], allow_integer=False))
        if amount_excl_idx is not None and amount_excl_idx < len(before_rate)
        else None
    )
    vat_amount = coerce_number(extract_first_numeric_token(after_rate[0], allow_integer=False))
    total = coerce_number(extract_first_numeric_token(after_rate[1], allow_integer=False))
    return {
        "line_number": line_number,
        "article": article,
        "description": description,
        "barcode": barcode,
        "quantity": quantity,
        "unit": unit,
        "unit_price_incl_vat": price,
        "amount_no_disc_incl_vat": amount_no_disc,
        "disc_amount": disc_amount,
        "amount_with_disc_excl_vat": amount_excl,
        "vat_rate": (_clean_inline_text(vat_rate_text) or "").replace(" ", ""),
        "vat_amount": vat_amount,
        "total_with_disc_incl_vat": total,
    }


def build_invoice_compact_numeric_tail_row(
    *,
    line_number: int | None,
    article: str | None,
    description: str | None,
    barcode: str | None,
    quantity: int | float | None,
    unit: str | None,
    price_text: Any,
    amount_excl_text: Any,
    vat_rate_text: Any,
    trailing_value_text: Any,
) -> dict[str, Any] | None:
    if quantity is None or not unit:
        return None

    unit_price = coerce_number(extract_first_numeric_token(price_text, allow_integer=False))
    amount_excl = coerce_number(extract_first_numeric_token(amount_excl_text, allow_integer=False))
    trailing_value = coerce_number(extract_first_numeric_token(trailing_value_text, allow_integer=False))
    if unit_price is None or amount_excl is None or trailing_value is None:
        return None

    amount_incl = None
    if unit_price is not None and quantity is not None:
        amount_incl = coerce_number(round(float(quantity) * float(unit_price), 2))

    vat_amount = None
    total = None
    if trailing_value >= amount_excl - 0.005:
        total = trailing_value
        vat_amount = coerce_number(round(max(float(total) - float(amount_excl), 0.0), 2))
    else:
        vat_amount = trailing_value
        total = coerce_number(round(float(amount_excl) + float(vat_amount), 2))

    return {
        "line_number": line_number,
        "article": article,
        "description": description,
        "barcode": barcode,
        "quantity": quantity,
        "unit": unit,
        "unit_price_incl_vat": unit_price,
        "amount_no_disc_incl_vat": amount_incl or total or amount_excl,
        "disc_amount": None,
        "amount_with_disc_excl_vat": amount_excl,
        "vat_rate": (_clean_inline_text(vat_rate_text) or "").replace(" ", ""),
        "vat_amount": vat_amount,
        "total_with_disc_incl_vat": total,
    }
