from __future__ import annotations

from src.modules.runtime_waybill_header import (
    build_waybill_header_crop_bbox,
    count_waybill_ocr_hits,
    extract_waybill_number_from_crop_text,
    is_waybill_candidate_by_layout,
)


def test_is_waybill_candidate_by_layout_requires_header_and_table() -> None:
    roi_items = [{"id": "header_box", "bbox": [0, 0, 100, 80]}]
    is_candidate, signals = is_waybill_candidate_by_layout(roi_items)
    assert is_candidate is False
    assert signals["has_header_box"] is True


def test_build_waybill_header_crop_bbox_uses_header_and_unp_cells() -> None:
    roi_items = [
        {"id": "header_box", "bbox": [0, 0, 1000, 180]},
        {"kind": "unp_cell", "bbox": [40, 190, 220, 240]},
        {"kind": "unp_cell", "bbox": [240, 190, 420, 240]},
    ]

    crop = build_waybill_header_crop_bbox({"width": 1000, "height": 1400}, roi_items)

    assert crop is not None
    assert crop[0] == 500
    assert crop[2] < 1000
    assert crop[1] < crop[3]


def test_extract_waybill_number_prefers_best_scored_candidate() -> None:
    ocr_items = [
        {"text": "12", "bbox": [50, 120, 80, 150]},
        {"text": "1234567", "bbox": [200, 180, 360, 220]},
        {"text": "12345", "bbox": [200, 20, 280, 50]},
    ]

    number = extract_waybill_number_from_crop_text("12345 1234567", ocr_items)

    assert number == "1234567"


def test_count_waybill_ocr_hits_matches_readable_cyrillic() -> None:
    text = "ТОВАРНАЯ НАКЛАДНАЯ\nСерия\nГрузоотправитель\nГрузополучатель"

    assert count_waybill_ocr_hits(text) >= 3
