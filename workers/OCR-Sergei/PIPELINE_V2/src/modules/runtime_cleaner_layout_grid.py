from __future__ import annotations

import cv2
import numpy as np

from src.modules.runtime_cleaner_page_objects import merge_close_values
from src.modules.runtime_cleaner_stage1 import prepare_binary_mask

RIGHT_BORDER_MIN_H_LEN = 80
RIGHT_BORDER_END_TOL = 12
RIGHT_BORDER_AGREE_RATIO = 0.35
RIGHT_BORDER_BAND = 8
RIGHT_BORDER_THICKNESS = 2
RIGHT_BORDER_RIGHT_ZONE_RATIO = 0.30

H_OPEN = 35
V_OPEN = 35
H_CLOSE = 12
V_CLOSE = 12

ROW_CLUSTER_TOL = 2
COL_CLUSTER_TOL = 3

MIN_ROW_COUNT = 4
MIN_H_LEN_ABS = 50
MIN_V_LEN_ABS = 35

from src.modules.runtime_cleaner_layout_detection import (
    build_axis_masks,
    extract_h_segments,
)

def restore_missing_left_col_from_rows(mask: np.ndarray, table_block: dict | None, thickness: int = 2) -> tuple[dict | None, dict]:
    """
    Рабочий и устойчивый способ восстановления левой границы:
    не рисуем линию в маску,
    а добавляем недостающий x в cols на основе начал строк.
    """
    if table_block is None:
        return table_block, {
            "restored": False,
            "left_x": None,
            "reason": "table_block is None",
        }

    rows = merge_close_values(table_block.get("rows", []), 3)
    cols = merge_close_values(table_block.get("cols", []), 3)

    if len(rows) < 2 or len(cols) < 2:
        return table_block, {
            "restored": False,
            "left_x": None,
            "reason": "not enough rows/cols",
        }

    y0, y1 = min(rows), max(rows)

    bin_img = prepare_binary_mask(mask)
    hmask, _ = build_axis_masks(bin_img)

    min_h_len = max(MIN_H_LEN_ABS, int(mask.shape[1] * 0.12))
    h_segments = extract_h_segments(hmask, min_h_len)

    starts: list[int] = []

    for y, xa, xb in h_segments:
        if not (y0 - 8 <= y <= y1 + 8):
            continue
        starts.append(int(xa))

    if len(starts) < 3:
        return table_block, {
            "restored": False,
            "left_x": None,
            "reason": "too few starts",
        }

    left_x = int(np.percentile(starts, 10))

    if abs(left_x - cols[0]) < 15:
        return table_block, {
            "restored": False,
            "left_x": cols[0],
            "reason": "already close",
        }

    new_cols = merge_close_values([left_x] + cols, 3)

    new_block = dict(table_block)
    new_block["cols"] = new_cols

    return new_block, {
        "restored": True,
        "left_x": left_x,
        "reason": "restored from row starts",
    }


def restore_right_border_from_horizontal_ends(
    mask: np.ndarray,
    table_block: dict,
    min_h_len: int = RIGHT_BORDER_MIN_H_LEN,
    end_tol: int = RIGHT_BORDER_END_TOL,
    agree_ratio: float = RIGHT_BORDER_AGREE_RATIO,
    right_zone_ratio: float = RIGHT_BORDER_RIGHT_ZONE_RATIO,
    band: int = RIGHT_BORDER_BAND,
    thickness: int = RIGHT_BORDER_THICKNESS,
) -> tuple[np.ndarray, list[int] | None, list[int] | None, dict]:
    """
    Восстанавливает правую вертикальную границу таблицы
    по правым концам горизонталей внутри найденного блока.
    """
    if table_block is None:
        return mask, None, None, {
            "restored": False,
            "reason": "table_block is None",
            "right_x": None,
            "share": 0.0,
        }

    rows = merge_close_values(table_block.get("rows", []), 3)
    cols = merge_close_values(table_block.get("cols", []), 3)

    if len(rows) < 2 or len(cols) < 2:
        return mask, rows, cols, {
            "restored": False,
            "reason": "not enough rows/cols in table_block",
            "right_x": None,
            "share": 0.0,
        }

    y0, y1 = int(min(rows)), int(max(rows))
    x0, x1 = int(min(cols)), int(max(cols))

    bin_img = prepare_binary_mask(mask)
    hmask, _ = build_axis_masks(bin_img)
    h_segments = extract_h_segments(hmask, min_h_len)

    table_w = max(1, x1 - x0)
    right_zone_x = x0 + int(table_w * right_zone_ratio)

    candidate_ends: list[int] = []
    used_segments: list[tuple[int, int, int]] = []

    for y, xa, xb in h_segments:
        seg_len = xb - xa + 1
        if seg_len < min_h_len:
            continue

        if not (y0 - band <= y <= y1 + band):
            continue

        if xb < right_zone_x:
            continue

        if xb < x0 - band or xa > x1 + band:
            continue

        candidate_ends.append(int(xb))
        used_segments.append((int(y), int(xa), int(xb)))

    if len(candidate_ends) < 3:
        return mask, rows, cols, {
            "restored": False,
            "reason": "too few horizontal candidates",
            "right_x": None,
            "share": 0.0,
            "candidate_count": len(candidate_ends),
        }

    ends = np.array(sorted(candidate_ends), dtype=np.int32)

    med = float(np.median(ends))
    mad = float(np.median(np.abs(ends - med))) + 1e-6

    keep = np.abs(ends - med) <= max(end_tol * 2, 2.5 * mad + 4)
    ends_kept = ends[keep]

    if len(ends_kept) < 3:
        ends_kept = ends

    share = len(ends_kept) / max(1, len(ends))

    if share < agree_ratio:
        return mask, rows, cols, {
            "restored": False,
            "reason": f"share too low after filtering: {share:.3f}",
            "right_x": None,
            "share": share,
            "candidate_count": len(candidate_ends),
            "all_ends": candidate_ends,
            "kept_ends": ends_kept.tolist(),
        }

    best_x = int(np.percentile(ends_kept, 85))

    out = mask.copy()
    cv2.line(out, (best_x, y0), (best_x, y1), 255, thickness)

    rows2 = merge_close_values(rows, 3)

    base_cols = merge_close_values(cols, 3)
    base_cols = [c for c in base_cols if abs(c - best_x) > 6]
    cols2 = merge_close_values(base_cols + [best_x], 3)

    if len(rows2) >= 2:
        rows2 = [r for r in rows2 if (y0 - band) <= r <= (y1 + band)]
        rows2 = merge_close_values(rows2 + [y0, y1], 3)
    else:
        rows2 = rows

    info = {
        "restored": True,
        "reason": "ok",
        "right_x": best_x,
        "share": share,
        "candidate_count": len(candidate_ends),
        "all_ends": candidate_ends,
        "kept_ends": ends_kept.tolist(),
        "used_segments": used_segments,
    }

    return out, rows2, cols2, info


def rebuild_grid(mask: np.ndarray, table_block: dict | None) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Итоговая схема восстановления:
    1) table_block уже может быть поправлен по left col
    2) восстанавливаем только правую границу
    3) строим финальный grid
    """
    if table_block is None:
        return np.zeros_like(mask), mask.copy(), {
            "right_restored": False,
            "right_x": None,
        }

    mask2, rows2, cols2, right_info = restore_right_border_from_horizontal_ends(mask, table_block)

    if rows2 is None or cols2 is None or len(rows2) < 2 or len(cols2) < 2:
        rows0 = merge_close_values(table_block.get("rows", []), 3)
        cols0 = merge_close_values(table_block.get("cols", []), 3)
        grid0 = build_grid_mask(mask.shape, rows0, cols0, thickness=2)
        return grid0, mask2, {
            "right_restored": bool(right_info.get("restored", False)),
            "right_x": right_info.get("right_x"),
            "right_reason": right_info.get("reason"),
        }

    grid = build_grid_mask(mask.shape, rows2, cols2, thickness=2)

    return grid, mask2, {
        "right_restored": bool(right_info.get("restored", False)),
        "right_x": right_info.get("right_x"),
        "right_reason": right_info.get("reason"),
    }


# =========================================================
# ЭТАП 2 — OVERLAY / FORM
# =========================================================

def build_grid_mask(shape: tuple[int, int], rows: list[int], cols: list[int], thickness: int = 2) -> np.ndarray:
    rows = merge_close_values(rows, 3)
    cols = merge_close_values(cols, 3)

    grid = np.zeros(shape, dtype=np.uint8)

    if len(rows) < 2 or len(cols) < 2:
        return grid

    x0, x1 = min(cols), max(cols)
    y0, y1 = min(rows), max(rows)

    for y in rows:
        cv2.line(grid, (x0, y), (x1, y), 255, thickness)

    for x in cols:
        cv2.line(grid, (x, y0), (x, y1), 255, thickness)

    return grid


__all__ = [
    "build_axis_masks",
    "build_grid_mask",
    "build_table_axis_masks",
    "col_horizontal_support",
    "count_intersections",
    "detect_layout_type",
    "detect_table_start_row_by_dense_verticals",
    "extract_h_segments",
    "extract_rows_cols_from_grid_mask",
    "extract_v_segments",
    "find_continuation_table_block",
    "find_main_table_block",
    "find_strict_table_block",
    "has_form_structure",
    "rebuild_grid",
    "restore_missing_left_col_from_rows",
    "restore_right_border_from_horizontal_ends",
    "row_vertical_support",
    "vertical_coverage",
]
