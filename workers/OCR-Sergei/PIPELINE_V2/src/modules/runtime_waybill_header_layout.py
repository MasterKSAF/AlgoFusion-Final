from __future__ import annotations

from typing import Any


def _roi_bbox_xyxy(roi: dict[str, Any]) -> tuple[int, int, int, int] | None:
    bbox = roi.get("bbox") or {}
    if isinstance(bbox, dict):
        try:
            return int(bbox["x1"]), int(bbox["y1"]), int(bbox["x2"]), int(bbox["y2"])
        except Exception:
            return None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    return None


def is_waybill_candidate_by_layout(roi_items: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    header_boxes = [item for item in roi_items if item.get("id") == "header_box"]
    unp_cells = [item for item in roi_items if item.get("kind") == "unp_cell"]
    header_form_rois = [item for item in roi_items if item.get("kind") == "header_form_roi"]
    table_cells = [item for item in roi_items if item.get("kind") == "table_cell"]

    signals = {
        "has_header_box": bool(header_boxes),
        "unp_cell_count": len(unp_cells),
        "header_form_roi_count": len(header_form_rois),
        "table_cell_count": len(table_cells),
    }
    is_candidate = (
        signals["has_header_box"]
        and signals["table_cell_count"] >= 10
        and (signals["unp_cell_count"] >= 2 or signals["header_form_roi_count"] >= 1)
    )
    signals["score"] = (
        int(signals["has_header_box"])
        + int(signals["table_cell_count"] >= 10)
        + int(signals["unp_cell_count"] >= 2 or signals["header_form_roi_count"] >= 1)
    )
    return is_candidate, signals


def build_waybill_header_crop_bbox(image_size: dict[str, Any], roi_items: list[dict[str, Any]]) -> list[int] | None:
    width = int((image_size or {}).get("width") or 0)
    height = int((image_size or {}).get("height") or 0)
    if width <= 0 or height <= 0:
        return None

    unp_cells = [item for item in roi_items if item.get("kind") == "unp_cell"]
    header_box = next((item for item in roi_items if item.get("id") == "header_box"), None)
    table_cells = [item for item in roi_items if item.get("kind") == "table_cell"]
    if len(unp_cells) < 2 or not header_box:
        return None

    header_bbox = _roi_bbox_xyxy(header_box)
    cell_boxes = [_roi_bbox_xyxy(item) for item in unp_cells]
    cell_boxes = [bbox for bbox in cell_boxes if bbox]
    table_boxes = [_roi_bbox_xyxy(item) for item in table_cells]
    table_boxes = [bbox for bbox in table_boxes if bbox]
    if not header_bbox or len(cell_boxes) < 2:
        return None

    hx1, hy1, hx2, hy2 = header_bbox
    header_h = max(1, hy2 - hy1)
    cell_y1 = min(box[1] for box in cell_boxes)
    cell_y2 = max(box[3] for box in cell_boxes)
    table_y1_candidates = [box[1] for box in table_boxes if box[1] > cell_y2 + 20]
    table_y1 = min(table_y1_candidates) if table_y1_candidates else None

    x1 = max(0, int(round(width * 0.5)))
    x2 = max(x1 + 1, int(round(width - (3.0 / 21.0) * width)))

    def _clamped_crop(raw_y1: int, raw_y2: int) -> list[int] | None:
        cx1 = max(0, min(width - 1, x1))
        cx2 = max(0, min(width, x2))
        cy1 = max(0, min(height - 1, raw_y1))
        cy2 = max(0, min(height, raw_y2))
        if cx2 - cx1 < 40 or cy2 - cy1 < 20:
            return None
        return [cx1, cy1, cx2, cy2]

    lower_bounds = [hy2 - 4]
    if table_y1 is not None:
        lower_bounds.append(table_y1 - 4)
    y1_below_unp = max(int(round(cell_y2 + 4)), int(round(hy1 + header_h * 0.18)))
    crop = _clamped_crop(y1_below_unp, int(round(min(lower_bounds))))
    if crop:
        return crop

    y1_above_unp = max(0, int(round(hy1 + header_h * 0.18)))
    y2_above_unp = int(round(cell_y1 - 4))
    crop = _clamped_crop(y1_above_unp, y2_above_unp)
    if crop:
        return crop

    y1_legacy = max(0, int(round(cell_y1 - header_h * 0.42)))
    y2_legacy = int(round(cell_y2 - 2))
    crop = _clamped_crop(y1_legacy, y2_legacy)
    if crop:
        return crop

    if table_y1 is None:
        return None
    return _clamped_crop(int(round(cell_y2 + 4)), int(round(table_y1 - 4)))


def build_waybill_header_crop_info(image_size: dict[str, Any], roi_items: list[dict[str, Any]]) -> dict[str, Any]:
    is_candidate, layout_signals = is_waybill_candidate_by_layout(roi_items)
    crop_bbox = build_waybill_header_crop_bbox(image_size, roi_items) if is_candidate else None
    return {
        "is_waybill_candidate_by_layout": bool(is_candidate),
        "layout_signals": layout_signals,
        "crop_bbox": crop_bbox,
    }
