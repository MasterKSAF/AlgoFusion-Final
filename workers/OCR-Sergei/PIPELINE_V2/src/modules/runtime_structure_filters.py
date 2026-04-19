from __future__ import annotations

import copy
from typing import Any

from src.modules.runtime_common import bbox_value, set_bbox_value


def apply_waybill_first_page_footer_guard(rois: list[dict[str, Any]], page_role: str, doc_type: str) -> list[dict[str, Any]]:
    if doc_type != "waybill" or page_role != "first":
        return rois

    footer_box = next((roi for roi in rois if roi.get("kind") == "footer_box"), None)
    table_cells = [roi for roi in rois if roi.get("kind") == "table_cell"]
    if not footer_box or not table_cells:
        return rois

    table_y2_max = max(bbox_value(roi, "y2") for roi in table_cells)
    footer_y1 = bbox_value(footer_box, "y1")
    gap = footer_y1 - table_y2_max

    if gap < 0 or gap > 24:
        return rois

    clip_y2 = max(0, table_y2_max - 16)
    new_footer_y1 = min(footer_y1, table_y2_max - 14)
    if new_footer_y1 <= 0 or clip_y2 <= 0:
        return rois

    guarded: list[dict[str, Any]] = []
    for roi in rois:
        current = copy.deepcopy(roi)
        if current.get("kind") == "footer_box":
            set_bbox_value(current, "y1", new_footer_y1)
        elif current.get("kind") == "table_cell" and bbox_value(current, "y2") >= table_y2_max - 2:
            y1 = bbox_value(current, "y1")
            if clip_y2 - y1 >= 24:
                set_bbox_value(current, "y2", clip_y2)
        guarded.append(current)
    return guarded


def filter_rois_by_page_role(
    rois: list[dict[str, Any]],
    *,
    doc_type: str | None,
    page_role: str | None,
    skip_filter: bool = False,
) -> list[dict[str, Any]]:
    if doc_type == "payment_order" or skip_filter:
        return rois

    filtered: list[dict[str, Any]] = []
    keep_footer_on_first_waybill = doc_type == "waybill" and page_role == "first"
    for roi in rois:
        kind = roi.get("kind")
        keep = True
        if page_role == "first":
            if kind == "footer_box" and not keep_footer_on_first_waybill:
                keep = False
        elif page_role == "middle":
            if kind in {"header_box", "footer_box", "header_form_roi", "unp_cell"}:
                keep = False
        elif page_role == "last":
            if kind in {"header_box", "header_form_roi", "unp_cell"}:
                keep = False
        if keep:
            filtered.append(roi)
    return filtered
