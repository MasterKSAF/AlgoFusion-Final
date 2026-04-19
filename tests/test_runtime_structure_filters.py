from __future__ import annotations

from src.modules.runtime_structure_filters import filter_rois_by_page_role


def test_filter_rois_by_page_role_removes_middle_page_header_and_footer_artifacts() -> None:
    rois = [
        {"kind": "header_box"},
        {"kind": "footer_box"},
        {"kind": "header_form_roi"},
        {"kind": "unp_cell"},
        {"kind": "table_cell"},
    ]

    filtered = filter_rois_by_page_role(rois, doc_type="invoice", page_role="middle")

    assert filtered == [{"kind": "table_cell"}]


def test_filter_rois_by_page_role_keeps_first_waybill_footer_box() -> None:
    rois = [{"kind": "footer_box"}, {"kind": "table_cell"}]

    filtered = filter_rois_by_page_role(rois, doc_type="waybill", page_role="first")

    assert filtered == rois
