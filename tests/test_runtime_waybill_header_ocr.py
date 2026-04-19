from __future__ import annotations

from src.modules.runtime_waybill_header_ocr import count_waybill_ocr_hits, extract_waybill_number_from_crop_text


def test_count_waybill_ocr_hits_matches_readable_cyrillic() -> None:
    text = "ТОВАРНАЯ НАКЛАДНАЯ\nСерия\nГрузоотправитель\nГрузополучатель"

    assert count_waybill_ocr_hits(text) >= 3


def test_extract_waybill_number_prefers_best_scored_candidate() -> None:
    ocr_items = [
        {"text": "12", "bbox": [50, 120, 80, 150]},
        {"text": "1234567", "bbox": [200, 180, 360, 220]},
        {"text": "12345", "bbox": [200, 20, 280, 50]},
    ]

    number = extract_waybill_number_from_crop_text("12345 1234567", ocr_items)

    assert number == "1234567"
