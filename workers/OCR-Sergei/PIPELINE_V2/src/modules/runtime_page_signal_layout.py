from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.modules.runtime_common import bbox_xyxy as _bbox_xyxy


@dataclass(frozen=True)
class PrecomputedPageLayoutSignals:
    layout_type: str
    layout_stats: dict[str, int | float]
    table_top_ratio: float | None
    has_footer_box: bool
    has_header_box: bool
    unp_cell_count: int


def analyze_precomputed_roi_layout(roi_payload: dict[str, Any] | None, page_height: int) -> PrecomputedPageLayoutSignals:
    rois = []
    if isinstance(roi_payload, dict):
        rois = roi_payload.get("ocr_targets") or roi_payload.get("rois") or []

    table_cells = [roi for roi in rois if roi.get("kind") == "table_cell"]
    footer_box = next((roi for roi in rois if roi.get("id") == "footer_box"), None)
    header_box = next((roi for roi in rois if roi.get("id") == "header_box"), None)
    form_like_rois = [roi for roi in rois if roi.get("kind") in {"form_roi", "header_form_roi", "unp_cell"}]
    unp_cell_count = sum(1 for roi in rois if roi.get("kind") == "unp_cell")

    row_bins: dict[int, int] = {}
    for roi in table_cells:
        bbox = _bbox_xyxy(roi)
        if not bbox:
            continue
        y1 = int(bbox[1])
        key = int(round(y1 / 12.0)) * 12
        row_bins.setdefault(key, 0)
        row_bins[key] += 1
    rows_n = len(row_bins)
    cols_n = max(row_bins.values()) if row_bins else 0
    layout_type = "table" if table_cells else ("form" if form_like_rois else "unknown")
    layout_stats = {
        "rows_n": rows_n,
        "cols_n": cols_n,
        "intersections": rows_n * cols_n,
        "density": round((len(table_cells) / max(1, rows_n * cols_n)), 4) if rows_n and cols_n else 0.0,
    }

    table_top = None
    if table_cells:
        table_top = min((_bbox_xyxy(roi) or (0, page_height, 0, page_height))[1] for roi in table_cells)
    table_top_ratio = round(table_top / page_height, 4) if table_top is not None and page_height > 0 else None

    return PrecomputedPageLayoutSignals(
        layout_type=layout_type,
        layout_stats=layout_stats,
        table_top_ratio=table_top_ratio,
        has_footer_box=bool(footer_box),
        has_header_box=header_box is not None,
        unp_cell_count=unp_cell_count,
    )
