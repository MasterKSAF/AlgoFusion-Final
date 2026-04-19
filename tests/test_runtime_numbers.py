from __future__ import annotations

from src.modules.runtime_numbers import (
    coerce_number,
    extract_first_numeric_token,
    maybe_integral_quantity,
    numeric_close,
    positive_number,
    to_float_soft,
)


def test_to_float_soft_parses_decimal_text() -> None:
    assert to_float_soft("12,34") == 12.34


def test_coerce_number_returns_int_for_whole_values() -> None:
    assert coerce_number(5.0) == 5


def test_numeric_close_allows_small_difference() -> None:
    assert numeric_close(10.0, 10.04)


def test_positive_number_respects_zero_flag() -> None:
    assert positive_number("0", allow_zero=False) is None
    assert positive_number("0", allow_zero=True) == 0.0


def test_maybe_integral_quantity_snaps_near_integer() -> None:
    assert maybe_integral_quantity(2.01) == 2.0


def test_extract_first_numeric_token_handles_ocr_lookalikes() -> None:
    assert extract_first_numeric_token("O12,50") == 12.5
    assert extract_first_numeric_token("7 25") == 7.25
    assert extract_first_numeric_token("abc 42", allow_integer=False) is None
