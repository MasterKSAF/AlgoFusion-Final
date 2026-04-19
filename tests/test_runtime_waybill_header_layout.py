from __future__ import annotations

from src.modules.runtime_waybill_header_layout import (
    build_waybill_header_crop_bbox,
    build_waybill_header_crop_info,
    is_waybill_candidate_by_layout,
)


def test_is_waybill_candidate_by_layout_counts_required_signals() -> None:
    roi_items = [
        {"id": "header_box", "bbox": [0, 0, 100, 80]},
        {"kind": "unp_cell", "bbox": [10, 90, 30, 110]},
        {"kind": "unp_cell", "bbox": [40, 90, 60, 110]},
    ] + [{"kind": "table_cell", "bbox": [i * 10, 150, i * 10 + 5, 170]} for i in range(10)]

    is_candidate, signals = is_waybill_candidate_by_layout(roi_items)

    assert is_candidate is True
    assert signals["score"] == 3


def test_build_waybill_header_crop_info_uses_crop_bbox_only_for_candidates() -> None:
    roi_items = [
        {"id": "header_box", "bbox": [0, 0, 1000, 180]},
        {"kind": "unp_cell", "bbox": [40, 190, 220, 240]},
        {"kind": "unp_cell", "bbox": [240, 190, 420, 240]},
    ] + [{"kind": "table_cell", "bbox": [i * 20, 300, i * 20 + 10, 340]} for i in range(10)]

    info = build_waybill_header_crop_info({"width": 1000, "height": 1400}, roi_items)

    assert info["is_waybill_candidate_by_layout"] is True
    assert build_waybill_header_crop_bbox({"width": 1000, "height": 1400}, roi_items) == info["crop_bbox"]
