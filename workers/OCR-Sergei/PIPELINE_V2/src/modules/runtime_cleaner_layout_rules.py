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

from src.modules.runtime_cleaner_axis_helpers import (
    extract_rows_cols_from_grid_mask,
    build_axis_masks,
    build_table_axis_masks,
    extract_h_segments,
    extract_v_segments,
    row_vertical_support,
    col_horizontal_support,
    vertical_coverage,
    count_intersections,
)

def detect_layout_type(mask: np.ndarray) -> tuple[str, dict]:
    bin_img = prepare_binary_mask(mask)

    hmask, vmask = build_axis_masks(bin_img)

    h_segments = extract_h_segments(hmask, 40)
    v_segments = extract_v_segments(vmask, 40)

    rows = merge_close_values([y for y, _, _ in h_segments], 3)
    cols = merge_close_values([x for x, _, _ in v_segments], 3)
    intersections = count_intersections(h_segments, v_segments, band=3)

    density = intersections / max(1, len(rows) * len(cols))

    if (
        len(rows) >= 6
        and len(cols) >= 4
        and (intersections > 60 or density > 0.25)
    ):
        return "table", {
            "rows_n": len(rows),
            "cols_n": len(cols),
            "intersections": intersections,
            "density": density,
        }

    return "form", {
        "rows_n": len(rows),
        "cols_n": len(cols),
        "intersections": intersections,
        "density": density,
    }


def has_form_structure(mask: np.ndarray) -> bool:
    bin_img = prepare_binary_mask(mask)

    hmask, vmask = build_axis_masks(bin_img)
    h_segments = extract_h_segments(hmask, 30)
    v_segments = extract_v_segments(vmask, 30)

    rows = merge_close_values([y for y, _, _ in h_segments], 3)
    cols = merge_close_values([x for x, _, _ in v_segments], 3)
    nonzero = int(np.count_nonzero(bin_img))

    return (
        nonzero > 500
        and (len(rows) >= 3 or len(cols) >= 2 or (len(h_segments) + len(v_segments)) >= 8)
    )


# =========================================================
# ЭТАП 2 — ПОИСК TABLE BLOCK
# =========================================================

def detect_table_start_row_by_dense_verticals(
    rows_all: list[int],
    v_segments: list[tuple[int, int, int]],
    cols_all: list[int],
    min_dense_support: int = 6,
    consecutive_rows: int = 2,
    band: int = 3,
) -> int | None:
    """
    Ищем первую строку, с которой начинается плотная вертикальная сетка.
    """
    if len(rows_all) < consecutive_rows:
        return None

    if not cols_all:
        return None

    x0, x1 = min(cols_all), max(cols_all)

    supports: list[tuple[int, int]] = []
    for r in rows_all:
        s = row_vertical_support(r, v_segments, x0, x1, band=band)
        supports.append((r, s))

    for i in range(len(supports) - consecutive_rows + 1):
        ok = True
        for j in range(consecutive_rows):
            if supports[i + j][1] < min_dense_support:
                ok = False
                break
        if ok:
            return supports[i][0]

    return None


def _select_candidate_cols(
    cols_all: list[int],
    h_segments: list[tuple[int, int, int]],
    y0: int,
    y1: int,
) -> list[int]:
    """
    Первый отбор колонок:
    - крайние колонки мягче
    - внутренние строже
    """
    cols: list[int] = []

    for col_idx, c in enumerate(cols_all):
        support = col_horizontal_support(c, h_segments, y0, y1, band=3)

        if col_idx == 0 or col_idx == len(cols_all) - 1:
            if support >= 1:
                cols.append(c)
            continue

        if support >= 2:
            cols.append(c)

    return cols


def _select_good_cols(
    cols: list[int],
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    y0g: int,
    y1g: int,
) -> list[int]:
    """
    Финальный отбор колонок:
    - крайние оставляем мягко
    - внутренние принимаем либо по coverage,
      либо по сильной горизонтальной поддержке внутри грида
    """
    good_cols: list[int] = []

    if not cols:
        return good_cols

    x0, x1 = cols[0], cols[-1]
    total_h = max(1, y1g - y0g + 1)

    for col_idx, c in enumerate(cols):
        h_support = col_horizontal_support(c, h_segments, y0g, y1g, band=3)
        coverage = vertical_coverage(c, v_segments, y0g, y1g, band=3)
        covered_px = coverage * total_h

        if h_support < 2:
            continue

        # крайние колонки оставляем как раньше
        if col_idx == 0 or col_idx == len(cols) - 1:
            good_cols.append(c)
            continue

        # обычное правило
        if coverage >= 0.8:
            good_cols.append(c)
            continue

        # новое fallback-правило:
        # внутренняя колонка внутри грида + очень сильная поддержка строками
        inside_grid = (x0 + 5) <= c <= (x1 - 5)

        if inside_grid and h_support >= 20 and covered_px >= 80:
            good_cols.append(c)
            continue

    return good_cols


def find_strict_table_block(mask: np.ndarray) -> dict | None:
    _, hmask, vmask = build_table_axis_masks(mask)
    h, w = mask.shape[:2]

    min_h_len = max(MIN_H_LEN_ABS, int(w * 0.12))
    min_v_len = max(MIN_V_LEN_ABS, int(h * 0.08))

    h_segments = extract_h_segments(hmask, min_h_len)
    v_segments = extract_v_segments(vmask, min_v_len)

    if not h_segments or not v_segments:
        return None

    rows_all = merge_close_values([y for y, _, _ in h_segments], ROW_CLUSTER_TOL)
    cols_all = merge_close_values([x for x, _, _ in v_segments], COL_CLUSTER_TOL)

    table_start_y = detect_table_start_row_by_dense_verticals(
        rows_all,
        v_segments,
        cols_all,
        min_dense_support=6,
        consecutive_rows=2,
        band=3,
    )

    if table_start_y is not None:
        rows_all = [r for r in rows_all if r >= table_start_y]

    if len(rows_all) < MIN_ROW_COUNT or len(cols_all) < 3:
        return None

    def search_with_support(required_support: int) -> dict | None:
        best = None

        for i in range(len(rows_all)):
            for j in range(i + MIN_ROW_COUNT - 1, len(rows_all)):
                rows = rows_all[i:j + 1]
                if not rows:
                    continue

                y0, y1 = rows[0], rows[-1]

                cols = _select_candidate_cols(cols_all, h_segments, y0, y1)
                if len(cols) < required_support:
                    continue

                x0, x1 = cols[0], cols[-1]

                good_rows = [
                    r for r in rows
                    if row_vertical_support(r, v_segments, x0, x1, band=3) >= required_support
                ]
                if len(good_rows) < MIN_ROW_COUNT:
                    continue

                y0g, y1g = good_rows[0], good_rows[-1]

                good_cols = _select_good_cols(cols, h_segments, v_segments, y0g, y1g)
                if len(good_cols) < required_support:
                    continue

                score = (
                    len(good_rows) * 100
                    + len(good_cols) * 25
                    + (good_rows[-1] - good_rows[0]) * 0.8
                    + (good_cols[-1] - good_cols[0]) * 0.15
                )

                item = {
                    "rows": good_rows,
                    "cols": good_cols,
                    "score": score,
                    "required_support": required_support,
                    "mode": "strict",
                }

                if best is None or item["score"] > best["score"]:
                    best = item

        return best

    best = search_with_support(4)
    if best is not None:
        return best

    return search_with_support(3)


def find_continuation_table_block(mask: np.ndarray) -> dict | None:
    _, hmask, vmask = build_table_axis_masks(mask)
    h, w = mask.shape[:2]

    min_h_len = max(50, int(w * 0.12))
    min_v_len = max(35, int(h * 0.08))

    h_segments = extract_h_segments(hmask, min_h_len)
    v_segments = extract_v_segments(vmask, min_v_len)

    if not h_segments or not v_segments:
        return None

    rows = merge_close_values([y for y, _, _ in h_segments], ROW_CLUSTER_TOL)
    cols_all = merge_close_values([x for x, _, _ in v_segments], COL_CLUSTER_TOL)

    if len(rows) < MIN_ROW_COUNT or len(cols_all) < 4:
        return None

    best_run: list[int] = []
    current = [rows[0]]

    for r_prev, r in zip(rows, rows[1:]):
        if abs(r - r_prev) <= max(80, int(h * 0.05)):
            current.append(r)
        else:
            if len(current) > len(best_run):
                best_run = current[:]
            current = [r]

    if len(current) > len(best_run):
        best_run = current[:]

    best_rows = best_run if len(best_run) >= MIN_ROW_COUNT else rows
    y0, y1 = best_rows[0], best_rows[-1]

    stable_cols: list[int] = []
    for c in cols_all:
        cov = vertical_coverage(c, v_segments, y0, y1, band=3)
        if cov >= 0.45:
            stable_cols.append(c)

    if len(stable_cols) < 4:
        stable_cols = []
        for c in cols_all:
            cov = vertical_coverage(c, v_segments, y0, y1, band=3)
            if cov >= 0.25:
                stable_cols.append(c)

    if len(stable_cols) < 4:
        return None

    x0, x1 = stable_cols[0], stable_cols[-1]

    filtered_rows: list[int] = []
    for r in best_rows:
        supports = 0
        for y, xa, xb in h_segments:
            if abs(y - r) <= 2:
                inter = max(0, min(xb, x1) - max(xa, x0) + 1)
                if inter >= max(40, int((x1 - x0) * 0.35)):
                    supports += 1
        if supports > 0:
            filtered_rows.append(r)

    if len(filtered_rows) < MIN_ROW_COUNT:
        return None

    score = len(filtered_rows) * 100 + len(stable_cols) * 30 + (filtered_rows[-1] - filtered_rows[0]) * 0.5

    return {
        "rows": filtered_rows,
        "cols": stable_cols,
        "score": score,
        "mode": "continuation",
    }


def find_main_table_block(mask: np.ndarray) -> dict | None:
    best = find_strict_table_block(mask)
    if best is not None:
        return best
    return find_continuation_table_block(mask)
