from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_common import strip_ocr_markup


WAYBILL_LINKED_NUMERIC_FIELDS = (
    "quantity",
    "price",
    "cost",
    "vat_rate",
    "vat_amount",
    "cost_with_vat",
)

INVOICE_LINKED_NUMERIC_FIELDS = (
    "quantity",
    "unit_price_incl_vat",
    "amount_no_disc_incl_vat",
    "amount_with_disc_excl_vat",
    "vat_rate",
    "vat_amount",
    "total_with_disc_incl_vat",
)


def to_float_soft(value: Any) -> float | None:
    if value is None:
        return None
    text = strip_ocr_markup(value)
    if not text:
        return None
    text = text.replace("O", "0").replace("О", "0")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text:
        return None
    if text.count(",") > 1 and "." not in text:
        text = text.replace(",", "", text.count(",") - 1)
    if text.count(".") > 1 and "," not in text:
        text = text.replace(".", "", text.count(".") - 1)
    text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def coerce_number(value: float | None) -> int | float | None:
    if value is None:
        return None
    if abs(value - round(value)) < 1e-6:
        return int(round(value))
    return round(float(value), 2)


def numeric_close(actual: float | None, expected: float | None, *, abs_tol: float = 0.05, rel_tol: float = 0.015) -> bool:
    if actual is None or expected is None:
        return False
    return abs(float(actual) - float(expected)) <= max(abs_tol, abs(float(expected)) * rel_tol)


def positive_number(value: Any, *, allow_zero: bool = False) -> float | None:
    number = to_float_soft(value)
    if number is None:
        return None
    if allow_zero:
        return number if number >= -1e-6 else None
    return number if number > 1e-6 else None


def extract_first_numeric_token(value: Any, *, allow_integer: bool = True) -> float | None:
    text = strip_ocr_markup(value)
    if not text:
        return None
    text = (
        text.replace("O", "0")
        .replace("\u041e", "0")
        .replace("o", "0")
        .replace("\u043e", "0")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )
    text = re.sub(r"(?<=\d)[C\u0421\u0441](?=\b)", "0", text)
    decimal_match = re.search(r"\d+[.,]\d{1,2}", text)
    if decimal_match:
        return to_float_soft(decimal_match.group(0))
    spaced_decimal = re.search(r"(\d+)\s+(\d{2})(?!\d)", text)
    if spaced_decimal:
        return to_float_soft(f"{spaced_decimal.group(1)},{spaced_decimal.group(2)}")
    if allow_integer:
        integer_match = re.search(r"(?<!\d)\d+(?!\d)", text)
        if integer_match:
            return to_float_soft(integer_match.group(0))
    return None


def maybe_integral_quantity(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    nearest = round(value)
    if abs(value - nearest) <= 0.03:
        return float(nearest)
    rounded = round(value, 3)
    return rounded if rounded > 0 else None
