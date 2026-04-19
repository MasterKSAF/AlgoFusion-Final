from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from src.modules.runtime_common import copy_if_exists
from src.modules.runtime_io import ensure_dir, read_json, save_png, write_json
from src.modules.runtime_segmentation import select_structure_profile
from src.modules.runtime_services import PipelineRuntimeServices
from src.modules.runtime_structure_filters import (
    apply_waybill_first_page_footer_guard as _apply_waybill_first_page_footer_guard_impl,
    filter_rois_by_page_role as _filter_rois_by_page_role_impl,
)
from src.modules.runtime_types import PageWorkItem


def apply_waybill_first_page_footer_guard(rois: list[dict[str, Any]], page_role: str, doc_type: str) -> list[dict[str, Any]]:
    return _apply_waybill_first_page_footer_guard_impl(rois, page_role, doc_type)


def _filter_rois_by_page_role(
    rois: list[dict[str, Any]],
    *,
    doc_type: str | None,
    page_role: str | None,
    skip_filter: bool = False,
) -> list[dict[str, Any]]:
    return _filter_rois_by_page_role_impl(rois, doc_type=doc_type, page_role=page_role, skip_filter=skip_filter)


def build_role_aware_structure(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    page_dir: Path,
    temp_stage2_dir: Path,
    roi_dir: Path | None = None,
) -> Path:
    temp_out = ensure_dir(temp_stage2_dir / item.page_id)
    stats = (item.signals or {}).get("layout_stats") or {}

    if item.segment_doc_type == "payment_order":
        ok = services.cleaner_layout.process_form_page(item.page_id, item.mask, item.clean_bgr, temp_out, stats)
        if not ok:
            raise RuntimeError(f"process_form_page failed for {item.page_id}")
        base_png = temp_out / f"{item.page_id}__form_red.png"
        base_json = temp_out / f"{item.page_id}__ocr.json"
    else:
        ok = services.cleaner_layout.process_table_page(item.page_id, item.mask, item.clean_bgr, temp_out, "table", stats)
        if not ok:
            raise RuntimeError(f"process_table_page failed for {item.page_id}")
        base_png = temp_out / f"{item.page_id}__grid_red.png"
        base_json = temp_out / f"{item.page_id}__ocr.json"
        copy_if_exists(temp_out / f"{item.page_id}__mask_with_restored_right.png", page_dir / "13_maskr.png")

    copy_if_exists(base_png, page_dir / "13_base.png")

    page_ocr = read_json(base_json)

    rois = copy.deepcopy(page_ocr.get("ocr_targets", []))
    rois = apply_waybill_first_page_footer_guard(rois, item.page_role or "", item.segment_doc_type or "")
    rois = _filter_rois_by_page_role(rois, doc_type=item.segment_doc_type, page_role=item.page_role)

    roi_payload = {
        "page_id": item.page_id,
        "doc_type": item.segment_doc_type,
        "page_role": item.page_role,
        "segment_id": item.segment_id,
        "clean_image": str(page_dir / "11_noln.png"),
        "source_mask_json": str(item.mask_json_path),
        "image_size": {
            "width": int(item.no_lines_bgr.shape[1]),
            "height": int(item.no_lines_bgr.shape[0]),
        },
        "rois": rois,
        "ocr_targets": rois,
    }
    roi_dir = roi_dir or page_dir
    roi_coords_path = write_json(roi_dir / f"{item.page_id}__roi_coords.json", roi_payload)
    item.roi_coords_path = roi_coords_path

    roi_overlay = services.roi_render.draw_rois_on_clean(item.no_lines_bgr, rois)
    save_png(page_dir / "14_roi.png", roi_overlay)
    if roi_dir != page_dir:
        save_png(roi_dir / f"{item.page_id}__clean_with_roi.png", roi_overlay)
    return roi_coords_path


def build_role_aware_structure_v2(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    page_dir: Path,
    temp_stage2_dir: Path,
    roi_dir: Path | None = None,
) -> Path:
    temp_out = ensure_dir(temp_stage2_dir / item.page_id)
    signals = item.signals or {}
    stats = signals.get("layout_stats") or {}
    layout_hint = signals.get("layout_type") or "table"
    structure_profile = select_structure_profile(item)
    mode_used = None

    if item.segment_doc_type == "payment_order":
        ok = services.cleaner_layout.process_form_page(item.page_id, item.mask, item.clean_bgr, temp_out, stats)
        if not ok:
            raise RuntimeError(f"process_form_page failed for {item.page_id}")
        base_png = temp_out / f"{item.page_id}__form_red.png"
        base_json = temp_out / f"{item.page_id}__ocr.json"
        mode_used = "form"
    else:
        ok = services.cleaner_layout.process_table_page(item.page_id, item.mask, item.clean_bgr, temp_out, layout_hint, stats)
        if ok:
            base_png = temp_out / f"{item.page_id}__grid_red.png"
            base_json = temp_out / f"{item.page_id}__ocr.json"
            copy_if_exists(temp_out / f"{item.page_id}__mask_with_restored_right.png", page_dir / "13_maskr.png")
            mode_used = "table"
        else:
            form_ok = False
            prefer_form_fallback = (
                layout_hint == "form"
                or layout_hint == "unknown"
                or services.cleaner_layout.has_form_structure(item.mask)
                or item.page_role in {"middle", "last"}
            )
            if prefer_form_fallback:
                form_ok = services.cleaner_layout.process_form_page(item.page_id, item.mask, item.clean_bgr, temp_out, stats)
            if not form_ok:
                raise RuntimeError(f"structure build failed for {item.page_id}")
            base_png = temp_out / f"{item.page_id}__form_red.png"
            base_json = temp_out / f"{item.page_id}__ocr.json"
            mode_used = "form_fallback"

    copy_if_exists(base_png, page_dir / "13_base.png")

    page_ocr = read_json(base_json)

    rois = copy.deepcopy(page_ocr.get("ocr_targets", []))
    rois = apply_waybill_first_page_footer_guard(rois, item.page_role or "", item.segment_doc_type or "")
    rois = _filter_rois_by_page_role(
        rois,
        doc_type=item.segment_doc_type,
        page_role=item.page_role,
        skip_filter=(mode_used == "form_fallback"),
    )

    roi_payload = {
        "page_id": item.page_id,
        "doc_type": item.segment_doc_type,
        "page_role": item.page_role,
        "segment_id": item.segment_id,
        "structure_profile": structure_profile,
        "structure_mode": mode_used,
        "clean_image": str(page_dir / "11_noln.png"),
        "source_mask_json": str(item.mask_json_path),
        "image_size": {
            "width": int(item.no_lines_bgr.shape[1]),
            "height": int(item.no_lines_bgr.shape[0]),
        },
        "rois": rois,
        "ocr_targets": rois,
    }
    roi_dir = roi_dir or page_dir
    roi_coords_path = write_json(roi_dir / f"{item.page_id}__roi_coords.json", roi_payload)
    item.roi_coords_path = roi_coords_path

    roi_overlay = services.roi_render.draw_rois_on_clean(item.no_lines_bgr, rois)
    save_png(page_dir / "14_roi.png", roi_overlay)
    if roi_dir != page_dir:
        save_png(roi_dir / f"{item.page_id}__clean_with_roi.png", roi_overlay)
    return roi_coords_path


def build_role_aware_structure_from_precomputed(
    services: PipelineRuntimeServices,
    item: PageWorkItem,
    page_dir: Path,
    precomputed_roi_payload: dict[str, Any],
) -> Path:
    structure_profile = select_structure_profile(item)
    rois = copy.deepcopy(precomputed_roi_payload.get("ocr_targets") or precomputed_roi_payload.get("rois") or [])
    rois = apply_waybill_first_page_footer_guard(rois, item.page_role or "", item.segment_doc_type or "")
    filtered = _filter_rois_by_page_role(rois, doc_type=item.segment_doc_type, page_role=item.page_role)

    roi_payload = copy.deepcopy(precomputed_roi_payload)
    roi_payload["page_id"] = item.page_id
    roi_payload["doc_type"] = item.segment_doc_type
    roi_payload["page_role"] = item.page_role
    roi_payload["segment_id"] = item.segment_id
    roi_payload["structure_profile"] = structure_profile
    roi_payload["structure_mode"] = "precomputed"
    roi_payload["clean_image"] = str(page_dir / f"{item.page_id}__clean.png")
    roi_payload["rois"] = filtered
    roi_payload["ocr_targets"] = filtered
    if "image_size" not in roi_payload:
        roi_payload["image_size"] = {
            "width": int(item.no_lines_bgr.shape[1]),
            "height": int(item.no_lines_bgr.shape[0]),
        }

    item.roi_coords_path = write_json(page_dir / f"{item.page_id}__roi_coords.json", roi_payload)
    roi_overlay = services.roi_render.draw_rois_on_clean(item.no_lines_bgr, filtered)
    save_png(page_dir / "14_roi.png", roi_overlay)
    save_png(page_dir / f"{item.page_id}__clean_with_roi.png", roi_overlay)
    return item.roi_coords_path
