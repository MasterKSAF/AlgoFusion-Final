from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.modules.runtime_cleaner_form import detect_header_form_rois_with_outer_rebuild
from src.modules.runtime_cleaner_layout import (
    extract_rows_cols_from_grid_mask,
    find_main_table_block,
    rebuild_grid,
    restore_missing_left_col_from_rows,
)
from src.modules.runtime_cleaner_page_objects import build_page_ocr_json, extend_cols_with_page_boxes
from src.modules.runtime_cleaner_unp import _cm_to_px, detect_unp_cells
from src.modules.runtime_cleaner_visuals import (
    detect_footer_last_text_y,
    detect_header_last_text_y,
    draw_footer_blue_box,
    draw_header_green_box,
    make_overlay_two_colors,
)

DPI = 200

def process_table_page(
    page_id: str,
    mask: np.ndarray,
    orig: np.ndarray,
    out_dir: Path,
    layout: str,
    stats: dict,
) -> bool:

    table_block = find_main_table_block(mask)
    table_block, left_fix_info = restore_missing_left_col_from_rows(mask, table_block)

    if table_block is None:
        return False

    grid_mask, mask_with_restored_right, rb_info = rebuild_grid(mask, table_block)

    rows, cols = extract_rows_cols_from_grid_mask(grid_mask)
    mode = table_block.get("mode", "table")

    if len(rows) < 2 or len(cols) < 2:
        return False

    table_top_y = int(min(rows))
    table_bottom_y = int(max(rows))


    # ---- detect header / unp above table ----
    header_mask = np.zeros_like(mask)
    header_mask[:table_top_y, :] = mask[:table_top_y, :]

    # сначала ищем UNP
    unp_cells = detect_unp_cells(mask, table_top_y, dpi=DPI, clean_bgr=orig)

    # если UNP найден, header_form_roi не строим
    # если UNP найден, header_form_roi не строим
    header_form_rois = []

    if not unp_cells:
        page_id_lc = str(page_id).lower()
        is_account_prot = ("account_prot" in page_id_lc) or ("account-protocol" in page_id_lc)

        header_form_rois = detect_header_form_rois_with_outer_rebuild(
            header_mask,
            dpi=DPI,
            min_h_len=20,
            min_v_len=20,
            min_area=100,
            use_outer_rebuild=is_account_prot,
        )



    footer_bottom_y = detect_footer_last_text_y(
        orig,
        table_bottom_y + _cm_to_px(0.3, DPI),
    )

    header_bottom_y = detect_header_last_text_y(
        orig,
        max(1, table_top_y - _cm_to_px(0.3, DPI)),
    )

    overlay = make_overlay_two_colors(
        orig,
        red_mask=grid_mask,
        green_mask=None,
    )

    overlay, header_box = draw_header_green_box(
        overlay,
        header_bottom_y=header_bottom_y,
        dpi=DPI,
    )

    overlay, footer_box = draw_footer_blue_box(
        overlay,
        table_bottom_y=table_bottom_y,
        footer_bottom_y=footer_bottom_y,
        dpi=DPI,
    )

    cols = extend_cols_with_page_boxes(
        cols,
        header_box=header_box,
        footer_box=footer_box,
        min_extra_width=120,
    )

    for x1, y1, x2, y2 in unp_cells:
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 165, 255), 3)

    out_png = out_dir / f"{page_id}__grid_red.png"
    out_mask_png = out_dir / f"{page_id}__mask_with_restored_right.png"

    cv2.imwrite(str(out_png), overlay)
    cv2.imwrite(str(out_mask_png), mask_with_restored_right)

    meta = {
        "page_id": page_id,
        "layout": layout,
        "layout_stats": stats,
        "table_mode": mode,
        "rows": rows,
        "cols": cols,
        "score": float(table_block.get("score", 0)),
        "table_top_y": table_top_y,
        "table_bottom_y": table_bottom_y,
        "header_box": header_box,
        "footer_box": footer_box,
    }

    (out_dir / f"{page_id}__meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ---------- OCR JSON ----------

    page_ocr = build_page_ocr_json(
        page_id=page_id,
        layout="table",
        image_shape=orig.shape,
        rows=rows,
        cols=cols,
        header_box=header_box,
        footer_box=footer_box,
        unp_cells=unp_cells,
        header_form_rois=header_form_rois,
    )

    (out_dir / f"{page_id}__ocr.json").write_text(
        json.dumps(page_ocr, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("saved:", out_png)
    print("saved:", out_dir / f"{page_id}__ocr.json")

    return True


__all__ = [
    "process_table_page",
]
