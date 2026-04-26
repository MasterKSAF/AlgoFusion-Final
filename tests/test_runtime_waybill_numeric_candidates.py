from __future__ import annotations

from src.modules.runtime_waybill_numeric_candidates import (
    dominant_waybill_repair_unit,
    normalize_waybill_raw_unit_token,
    waybill_extract_total_before_note,
    waybill_find_tail_unit_with_end,
    waybill_numeric_token_values,
    waybill_parse_inline_numeric_tail,
    waybill_parse_numeric_candidate_from_text,
    waybill_parse_percent_text,
)

def test_waybill_parse_percent_text_accepts_supported_rates() -> None:
    assert waybill_parse_percent_text("20 %") == "20%"
    assert waybill_parse_percent_text("7 %") is None


def test_normalize_waybill_raw_unit_token_handles_noisy_ocr_variants() -> None:
    expected = normalize_waybill_raw_unit_token("wr")
    assert expected is not None
    assert normalize_waybill_raw_unit_token("wt") == expected


def test_dominant_waybill_repair_unit_prefers_frequent_value() -> None:
    expected = normalize_waybill_raw_unit_token("wr")
    assert dominant_waybill_repair_unit([{"unit": "wr"}, {"unit": "wt"}, {"unit": "kg"}]) == expected


def test_waybill_numeric_token_values_extracts_short_numeric_tail() -> None:
    assert waybill_numeric_token_values("2 60,00 120,00 20% 20,00 140,00")[:3] == [2.0, 60.0, 120.0]


def test_waybill_find_tail_unit_with_end_detects_last_unit_token() -> None:
    unit, end = waybill_find_tail_unit_with_end("item wr 2 60,00")

    assert unit == normalize_waybill_raw_unit_token("wr")
    assert isinstance(end, int)


def test_waybill_parse_numeric_candidate_from_text_returns_none_for_unsupported_shape() -> None:
    assert waybill_parse_numeric_candidate_from_text("товар wr 2 60,00 120,00 20% 20,00 140,00") is None


def test_waybill_extract_total_before_note_ignores_nonmatching_text() -> None:
    assert waybill_extract_total_before_note("140,00 | цена отпускн") is None


def test_waybill_extract_total_before_note_requires_vat_context() -> None:
    assert waybill_extract_total_before_note("шт 2 60,00 120,00 20% 20,00 140,00 | цена отпускн") == 140


def test_waybill_parse_inline_numeric_tail_parses_compact_row_tail() -> None:
    row = waybill_parse_inline_numeric_tail("wr 2 60,00 120,00 20% 20,00 140,00")

    assert row is not None
    assert row["unit"] == normalize_waybill_raw_unit_token("wr")
    assert row["quantity"] == 2
    assert row["cost_with_vat"] == 140
