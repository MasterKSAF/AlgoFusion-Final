from __future__ import annotations

from src.modules.runtime_roi_assignment_waybill_table import split_line_by_waybill_table_rois


def test_waybill_header_digit_prefers_unp_cell_over_header_box() -> None:
    item = {"text": "690667789", "bbox": [715, 131, 820, 149]}
    rois = [
        {"id": "header_box", "kind": "header_box", "bbox": {"x1": 39, "y1": 39, "x2": 1615, "y2": 617}},
        {"id": "unp_cell_003", "kind": "unp_cell", "bbox": {"x1": 663, "y1": 127, "x2": 872, "y2": 157}},
        {"id": "table_cell_0001", "kind": "table_cell", "bbox": {"x1": 100, "y1": 640, "x2": 200, "y2": 700}},
    ]

    parts = split_line_by_waybill_table_rois(item, rois)

    assert parts == [(rois[1], "690667789")]


def test_waybill_header_label_prefers_unp_cell_over_header_box() -> None:
    item = {"text": "Грузополучатель", "bbox": [893, 97, 1058, 117]}
    rois = [
        {"id": "header_box", "kind": "header_box", "bbox": {"x1": 39, "y1": 39, "x2": 1615, "y2": 617}},
        {"id": "unp_cell_002", "kind": "unp_cell", "bbox": {"x1": 872, "y1": 87, "x2": 1080, "y2": 127}},
        {"id": "table_cell_0001", "kind": "table_cell", "bbox": {"x1": 100, "y1": 640, "x2": 200, "y2": 700}},
    ]

    parts = split_line_by_waybill_table_rois(item, rois)

    assert parts == [(rois[1], "Грузополучатель")]
