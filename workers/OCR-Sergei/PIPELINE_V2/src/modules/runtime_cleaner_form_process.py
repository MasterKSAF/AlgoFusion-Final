from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.modules.runtime_cleaner_layout import build_axis_masks, extract_h_segments, extract_v_segments
from src.modules.runtime_cleaner_page_objects import build_page_ocr_json, merge_close_values
from src.modules.runtime_cleaner_stage1 import prepare_binary_mask

DPI = 200

from src.modules.runtime_cleaner_form_geometry import (
    detect_form_closed_regions,
    _mm_to_px,
    merge_nearby_h_segments,
    merge_nearby_v_segments,
    extract_form_geometry_segments,
    detect_header_form_rois_with_outer_rebuild,
    draw_form_geometry_overlay,
    _pick_outer_form_lines,
    _is_lower_right_local_form_hline,
    extend_horizontal_segments_to_outer_verticals,
    _build_outer_rect_from_picked_lines,
    _draw_outer_rect_on_overlay,
)

def process_form_page(
    page_id: str,
    mask: np.ndarray,
    orig: np.ndarray,
    out_dir: Path,
    stats: dict,
) -> bool:
    h_segments, v_segments = extract_form_geometry_segments(
        mask,
        dpi=DPI,
        min_h_len=30,
        min_v_len=30,
    )

    picked = _pick_outer_form_lines(
        h_segments,
        v_segments,
        min_h_len=60,
        min_v_len=60,
    )

    outer_rect = _build_outer_rect_from_picked_lines(
        picked,
        shape=mask.shape,
    )

    h_segments_ext = extend_horizontal_segments_to_outer_verticals(
        h_segments,
        picked,
        outer_rect=outer_rect,
    )

    overlay = draw_form_geometry_overlay(
        orig,
        h_segments_ext,
        v_segments,
        color=(0, 0, 255),
        thickness=2,
    )

    overlay = _draw_outer_rect_on_overlay(
        overlay,
        outer_rect,
        color=(0, 0, 255),
        thickness=2,
    )

    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    # >>> ВОТ ЭТОГО У ТЕБЯ НЕ ХВАТАЛО
    form_rois = detect_form_closed_regions(
        mask,
        h_segments_ext,
        v_segments,
        outer_rect=outer_rect,
        min_area=100,
    )

    out_png = out_dir / f"{page_id}__form_red.png"
    out_meta_json = out_dir / f"{page_id}__meta.json"
    out_ocr_json = out_dir / f"{page_id}__ocr.json"

    cv2.imwrite(str(out_png), overlay)

    meta = {
        "page_id": page_id,
        "layout": "form",
        "layout_stats": stats,
        "reason": "detected as form",
        "render_mode": "geometry_segments_red_2px_plus_outer_rect_plus_extended_hlines",
        "h_segments_n": len(h_segments),
        "h_segments_extended_n": len(h_segments_ext),
        "v_segments_n": len(v_segments),
        "outer_lines_found": picked is not None,
        "outer_rect_found": outer_rect is not None,
        "outer_rect": None if outer_rect is None else [int(v) for v in outer_rect],
        "outer_top_line": None if picked is None else [int(v) for v in picked["top"]],
        "outer_bottom_line": None if picked is None else [int(v) for v in picked["bottom"]],
        "outer_left_line": None if picked is None else [int(v) for v in picked["left"]],
        "outer_right_line": None if picked is None else [int(v) for v in picked["right"]],
        "form_rois_n": len(form_rois),
    }

    out_meta_json.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    page_ocr = build_page_ocr_json(
        page_id=page_id,
        layout="form",
        image_shape=orig.shape,
        outer_rect=outer_rect,
        form_rois=form_rois,
        extra_meta={
            "render_mode": meta["render_mode"],
            "outer_lines_found": meta["outer_lines_found"],
            "outer_rect_found": meta["outer_rect_found"],
            "form_rois_n": len(form_rois),
        },
    )

    out_ocr_json.write_text(
        json.dumps(page_ocr, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("outer_lines_found:", picked is not None)
    print("outer_rect_found :", outer_rect is not None)
    print("form_rois_found  :", len(form_rois))
    print("saved:", out_png)
    print("saved:", out_meta_json)
    print("saved:", out_ocr_json)
    return True


__all__ = [
    "detect_form_closed_regions",
    "detect_header_form_rois_with_outer_rebuild",
    "draw_form_geometry_overlay",
    "extract_form_geometry_segments",
    "process_form_page",
]
