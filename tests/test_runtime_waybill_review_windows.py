from __future__ import annotations

from src.modules.runtime_waybill_review_windows import (
    extract_waybill_barcode_from_name,
    waybill_find_review_row_index,
    waybill_iter_review_row_windows,
    waybill_significant_name_tokens,
)


def test_extract_waybill_barcode_from_name_finds_embedded_barcode() -> None:
    assert extract_waybill_barcode_from_name("Шампунь 4810123456789 250 мл") == "4810123456789"


def test_waybill_significant_name_tokens_drops_common_noise() -> None:
    tokens = waybill_significant_name_tokens("Товар Luxury Shampoo Estel Repair Complex")

    assert "shampoo" in tokens
    assert "repair" in tokens
    assert "complex" in tokens
    assert "luxury" not in tokens


def test_waybill_find_review_row_index_prefers_barcode_match() -> None:
    lines = [
        "строка 1",
        "Шампунь 4810123456789 2 шт 60,00 20%",
        "итого",
    ]

    idx = waybill_find_review_row_index(lines, {"name": "Шампунь 4810123456789"})

    assert idx == 1


def test_waybill_iter_review_row_windows_builds_unique_context_windows() -> None:
    lines = [
        "верх",
        "строка до",
        "Repair Complex Mask",
        "строка после",
        "низ",
    ]

    windows = waybill_iter_review_row_windows(lines, {"name": "Repair Complex"})

    assert windows[0] == ["Repair Complex Mask"]
    assert ["строка до", "Repair Complex Mask"] in windows
    assert ["Repair Complex Mask", "строка после"] in windows
