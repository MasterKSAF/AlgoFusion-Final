from __future__ import annotations

from pathlib import Path
from typing import Any

from src.modules.runtime_io import read_json, save_png, write_json
from src.modules.runtime_render import pil_from_bgr
from src.modules.runtime_services import RawOcrService
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_header_ocr import (
    count_waybill_ocr_hits as _count_waybill_ocr_hits_impl,
    extract_waybill_number_from_crop_text as _extract_waybill_number_from_crop_text_impl,
)
from src.modules.runtime_waybill_header_layout import (
    build_waybill_header_crop_bbox as _build_waybill_header_crop_bbox_impl,
    build_waybill_header_crop_info as _build_waybill_header_crop_info_impl,
    is_waybill_candidate_by_layout as _is_waybill_candidate_by_layout_impl,
)


def is_waybill_candidate_by_layout(roi_items: list[dict[str, Any]]) -> tuple[bool, dict[str, Any]]:
    return _is_waybill_candidate_by_layout_impl(roi_items)


def build_waybill_header_crop_bbox(image_size: dict[str, Any], roi_items: list[dict[str, Any]]) -> list[int] | None:
    return _build_waybill_header_crop_bbox_impl(image_size, roi_items)


def build_waybill_header_crop_info(image_size: dict[str, Any], roi_items: list[dict[str, Any]]) -> dict[str, Any]:
    return _build_waybill_header_crop_info_impl(image_size, roi_items)


def count_waybill_ocr_hits(full_text: str) -> int:
    return _count_waybill_ocr_hits_impl(full_text)


def extract_waybill_number_from_crop_text(full_text: str, ocr_items: list[dict[str, Any]]) -> str | None:
    return _extract_waybill_number_from_crop_text_impl(full_text, ocr_items)


def run_waybill_header_crop_ocr(
    raw_ocr: RawOcrService,
    item: PageWorkItem,
    roi_coords_path: Path,
    roi_dir: Path,
    page_dir: Path,
) -> Path | None:
    if item.segment_doc_type != "waybill" or item.page_role not in {"first", "single"}:
        return None
    raw_ocr.ensure_available()

    roi_payload = read_json(roi_coords_path)
    rois = roi_payload.get("ocr_targets") or roi_payload.get("rois") or []
    crop_info = build_waybill_header_crop_info(roi_payload.get("image_size") or {}, rois)

    output_path = roi_dir / f"{item.page_id}__waybill_header_ocr.json"
    if not crop_info.get("is_waybill_candidate_by_layout") or not crop_info.get("crop_bbox"):
        payload = {
            "page_id": item.page_id,
            **crop_info,
            "is_waybill_confirmed_by_ocr": False,
            "full_text": "",
            "ocr_items": [],
            "source_mode": "none",
        }
        item.header_ocr_json_path = write_json(output_path, payload)
        return item.header_ocr_json_path

    x1, y1, x2, y2 = crop_info["crop_bbox"]
    source_bgr = item.source_bgr
    src_h, src_w = source_bgr.shape[:2]
    roi_size = roi_payload.get("image_size") or {}
    roi_w = max(1, int(roi_size.get("width") or 0))
    roi_h = max(1, int(roi_size.get("height") or 0))
    sx = src_w / roi_w if roi_w > 0 else 1.0
    sy = src_h / roi_h if roi_h > 0 else 1.0
    sx1 = max(0, min(src_w - 1, int(round(x1 * sx))))
    sx2 = max(0, min(src_w, int(round(x2 * sx))))
    sy1 = max(0, min(src_h - 1, int(round(y1 * sy))))
    sy2 = max(0, min(src_h, int(round(y2 * sy))))
    crop_bgr = source_bgr[sy1:sy2, sx1:sx2]
    if crop_bgr.size == 0:
        payload = {
            "page_id": item.page_id,
            **crop_info,
            "is_waybill_confirmed_by_ocr": False,
            "full_text": "",
            "ocr_items": [],
            "source_mode": "empty_crop",
        }
        item.header_ocr_json_path = write_json(output_path, payload)
        return item.header_ocr_json_path

    save_png(page_dir / "14a_waybill_header_crop.png", crop_bgr)
    save_png(roi_dir / f"{item.page_id}__waybill_header_crop.png", crop_bgr)

    ocr_items = raw_ocr.run_image(pil_from_bgr(crop_bgr))
    full_text = "\n".join(str(row.get("text", "")).strip() for row in ocr_items if row.get("text")).strip()
    header_number = extract_waybill_number_from_crop_text(full_text, ocr_items)
    hits = count_waybill_ocr_hits(full_text)
    payload = {
        "page_id": item.page_id,
        **crop_info,
        "source_mode": "source_bgr",
        "source_crop_bbox": [sx1, sy1, sx2, sy2],
        "full_text": full_text,
        "ocr_items": ocr_items,
        "header_doc_number": header_number,
        "is_waybill_confirmed_by_ocr": bool(header_number or hits >= 2),
    }
    item.header_ocr_json_path = write_json(output_path, payload)
    return item.header_ocr_json_path
