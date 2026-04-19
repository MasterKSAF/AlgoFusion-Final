from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_articles import clean_invoice_description_value
from src.modules.runtime_invoice_cells import (
    looks_like_integer_text,
    looks_like_money_text,
    looks_like_percent_text,
)
from src.modules.runtime_invoice_units import normalize_invoice_unit_v2
from src.modules.runtime_numbers import coerce_number, extract_first_numeric_token
from src.modules.runtime_text_quality import _clean_inline_text


def parse_standard_invoice_region_nonempty(
    nonempty: list[str],
    fallback_line_number: int,
) -> dict[str, Any] | None:
    if not (
        len(nonempty) == 11
        and looks_like_integer_text(nonempty[0])
        and bool(re.search(r"\d{8,14}", nonempty[3]))
        and looks_like_integer_text(nonempty[4])
        and normalize_invoice_unit_v2(nonempty[5]) is not None
        and looks_like_money_text(nonempty[6])
        and looks_like_money_text(nonempty[7])
        and looks_like_percent_text(nonempty[8])
        and looks_like_money_text(nonempty[9])
        and looks_like_money_text(nonempty[10])
    ):
        return None

    quantity = coerce_number(extract_first_numeric_token(nonempty[4]))
    unit = normalize_invoice_unit_v2(nonempty[5]) or "шт"
    unit_price = coerce_number(extract_first_numeric_token(nonempty[6], allow_integer=False))
    amount_excl = coerce_number(extract_first_numeric_token(nonempty[7], allow_integer=False))
    vat_amount = coerce_number(extract_first_numeric_token(nonempty[9], allow_integer=False))
    total = coerce_number(extract_first_numeric_token(nonempty[10], allow_integer=False))
    amount_incl = None
    if quantity is not None and unit_price is not None:
        amount_incl = coerce_number(round(float(quantity) * float(unit_price), 2))

    line_number_token = extract_first_numeric_token(nonempty[0])
    article = _clean_inline_text(nonempty[1])
    return {
        "line_number": int(float(nonempty[0])) if line_number_token is not None else fallback_line_number,
        "article": article,
        "description": clean_invoice_description_value(nonempty[2], article=article),
        "barcode": re.search(r"(\d{8,14})", nonempty[3]).group(1),
        "quantity": quantity,
        "unit": unit,
        "unit_price_incl_vat": unit_price,
        "amount_no_disc_incl_vat": amount_incl or total,
        "disc_amount": None,
        "amount_with_disc_excl_vat": amount_excl,
        "vat_rate": (_clean_inline_text(nonempty[8]) or "").replace(" ", ""),
        "vat_amount": vat_amount,
        "total_with_disc_incl_vat": total,
    }
