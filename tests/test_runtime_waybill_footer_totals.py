from __future__ import annotations

from src.modules.runtime_waybill_footer_totals import (
    extract_waybill_footer_totals_from_text,
    normalize_waybill_total_number,
    parse_waybill_footer_numeric_token,
    waybill_totals_incoherent,
)


def test_parse_waybill_footer_numeric_token_handles_grouping_and_decimals() -> None:
    assert parse_waybill_footer_numeric_token("1 234,50") == 1234.5
    assert parse_waybill_footer_numeric_token("20") == 20
    assert parse_waybill_footer_numeric_token("abc") is None


def test_normalize_waybill_total_number_keeps_integral_values_clean() -> None:
    assert normalize_waybill_total_number(20.0) == 20
    assert normalize_waybill_total_number(20.25) == 20.25


def test_extract_waybill_footer_totals_from_text_reads_three_value_footer() -> None:
    text = (
        "Итого 5 100,00 20,00 120,00 "
        "Всего сумма НДС"
    )

    totals = extract_waybill_footer_totals_from_text(text)

    assert totals["quantity_total"] == 5
    assert totals["vat_total"] == 20
    assert totals["cost_total"] == 100
    assert totals["cost_with_vat_total"] == 120


def test_waybill_totals_incoherent_flags_broken_relation() -> None:
    assert waybill_totals_incoherent(1, 100, 25, 120) is True
    assert waybill_totals_incoherent(1, 100, 20, 120) is False
