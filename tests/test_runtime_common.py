from __future__ import annotations

from src.modules.runtime_common import (
    bbox_xyxy,
    doc_stem_from_page_id,
    page_no_from_page_id,
    strip_ocr_markup,
)


def test_bbox_xyxy_handles_dict_bbox() -> None:
    roi = {"bbox": {"x1": 10, "y1": 20, "x2": 30, "y2": 40}}
    assert bbox_xyxy(roi) == (10, 20, 30, 40)


def test_bbox_xyxy_handles_list_bbox() -> None:
    roi = {"bbox": [1, 2, 3, 4]}
    assert bbox_xyxy(roi) == (1, 2, 3, 4)


def test_page_id_helpers() -> None:
    assert page_no_from_page_id("Waybill_22__p0002") == 2
    assert doc_stem_from_page_id("Waybill_22__p0002") == "Waybill_22"


def test_strip_ocr_markup_compacts_spaces() -> None:
    assert strip_ocr_markup("<b>Text</b>   123") == "Text 123"
