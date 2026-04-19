from __future__ import annotations

from src.modules.runtime_structure import apply_waybill_first_page_footer_guard


def test_footer_guard_clips_bottom_row_on_first_waybill_page() -> None:
    rois = [
        {"kind": "table_cell", "bbox": {"x1": 10, "y1": 100, "x2": 100, "y2": 200}},
        {"kind": "table_cell", "bbox": {"x1": 110, "y1": 100, "x2": 200, "y2": 200}},
        {"kind": "footer_box", "bbox": {"x1": 0, "y1": 214, "x2": 300, "y2": 260}},
    ]

    guarded = apply_waybill_first_page_footer_guard(rois, "first", "waybill")

    assert guarded[0]["bbox"]["y2"] == 184
    assert guarded[1]["bbox"]["y2"] == 184
    assert guarded[2]["bbox"]["y1"] == 186


def test_footer_guard_leaves_non_waybill_pages_unchanged() -> None:
    rois = [{"kind": "footer_box", "bbox": {"x1": 0, "y1": 214, "x2": 300, "y2": 260}}]

    guarded = apply_waybill_first_page_footer_guard(rois, "first", "invoice")

    assert guarded == rois
