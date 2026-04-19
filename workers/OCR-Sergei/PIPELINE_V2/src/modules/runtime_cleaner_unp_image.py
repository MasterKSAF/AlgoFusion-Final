from __future__ import annotations

import cv2
import numpy as np

from src.modules.runtime_cleaner_page_objects import merge_close_values
from src.modules.runtime_cleaner_unp_segments import _cm_to_px


def _detect_unp_cells_from_clean_image(
    clean_bgr: np.ndarray | None,
    table_top_y: int,
    dpi: int = 200,
):
    if clean_bgr is None or clean_bgr.size == 0:
        return []

    if clean_bgr.ndim == 3:
        gray = cv2.cvtColor(clean_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = clean_bgr.copy()

    H, W = gray.shape[:2]
    if H <= 0 or W <= 0:
        return []

    # UNP-блок может лежать заметно выше таблицы на бланках с высокой шапкой,
    # поэтому ищем его во всей верхней части страницы до таблицы.
    y0 = 0
    y1 = max(20, table_top_y - 20)
    x0 = int(W * 0.18)
    x1 = int(W * 0.92)

    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return []

    _, inv_fixed = cv2.threshold(roi, 210, 255, cv2.THRESH_BINARY_INV)
    _, inv_otsu = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    inv = cv2.bitwise_or(inv_fixed, inv_otsu)

    h_kernel_w = max(15, _cm_to_px(0.18, dpi))
    v_kernel_h = max(10, _cm_to_px(0.12, dpi))

    h_mask = cv2.morphologyEx(
        inv,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_w, 1)),
    )
    v_mask = cv2.morphologyEx(
        inv,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_h)),
    )

    num_labels_h, labels_h, stats_h, _ = cv2.connectedComponentsWithStats(h_mask, 8)
    h_comps = []
    for i in range(1, num_labels_h):
        x, y, w, h, area = stats_h[i]
        if area < 20:
            continue
        if w < max(60, int(roi.shape[1] * 0.18)):
            continue
        if w > int(roi.shape[1] * 0.70):
            continue
        if h > max(8, int(roi.shape[0] * 0.15)):
            continue
        if y > int(roi.shape[0] * 0.35):
            continue
        h_comps.append({
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
            "area": int(area),
        })

    if len(h_comps) < 2:
        return []

    max_h_w = max(comp["w"] for comp in h_comps)
    strong_h = [comp for comp in h_comps if comp["w"] >= int(round(max_h_w * 0.70))]
    if len(strong_h) < 2:
        return []

    strong_h.sort(key=lambda comp: comp["y"] + comp["h"] / 2.0)
    line_y_centers = merge_close_values(
        [int(round(comp["y"] + comp["h"] / 2.0)) for comp in strong_h],
        6,
    )
    if len(line_y_centers) < 2:
        return []

    top_y = int(line_y_centers[0])
    bottom_y = int(line_y_centers[-1])
    if bottom_y - top_y < max(18, _cm_to_px(0.18, dpi)):
        return []

    if len(line_y_centers) >= 3:
        middle_y = min(
            line_y_centers[1:-1],
            key=lambda value: abs(value - (top_y + bottom_y) / 2.0),
        )
    else:
        middle_y = int(round((top_y + bottom_y) / 2.0))

    selected_h = []
    for target_y in (top_y, middle_y, bottom_y):
        candidates = [
            comp for comp in strong_h
            if abs(int(round(comp["y"] + comp["h"] / 2.0)) - target_y) <= 8
        ]
        if candidates:
            selected_h.append(max(candidates, key=lambda comp: comp["w"]))

    if len(selected_h) < 2:
        return []

    box_x1 = int(round(np.median([comp["x"] for comp in selected_h])))
    box_x2 = int(round(np.median([comp["x"] + comp["w"] - 1 for comp in selected_h])))
    if box_x2 - box_x1 < max(120, _cm_to_px(1.5, dpi)):
        return []

    num_labels_v, labels_v, stats_v, _ = cv2.connectedComponentsWithStats(v_mask, 8)
    min_v_h = max(12, int(round((bottom_y - top_y) * 0.75)))
    v_candidates = []
    for i in range(1, num_labels_v):
        x, y, w, h, area = stats_v[i]
        if area < 10:
            continue
        if h < min_v_h:
            continue
        if w > 6:
            continue
        x_center = int(round(x + w / 2.0))
        y_start = int(y)
        y_end = int(y + h - 1)
        if y_start > top_y + 6 or y_end < bottom_y - 6:
            continue
        if x_center < box_x1 - 10 or x_center > box_x2 + 10:
            continue
        v_candidates.append({
            "x": x_center,
            "h": int(h),
            "area": int(area),
        })

    if len(v_candidates) < 3:
        return []

    clustered_v = merge_close_values([cand["x"] for cand in v_candidates], 8)
    if len(clustered_v) < 3:
        return []

    left_x = min(clustered_v, key=lambda x: abs(x - box_x1))
    right_x = min(clustered_v, key=lambda x: abs(x - box_x2))
    if right_x - left_x < max(120, _cm_to_px(1.5, dpi)):
        return []

    inner_xs = [x for x in clustered_v if left_x + 20 < x < right_x - 20]
    if not inner_xs:
        return []

    line_ys = [top_y, middle_y, bottom_y]
    line_ys = merge_close_values(line_ys, 6)
    if len(line_ys) < 3:
        return []
    top_y, middle_y, bottom_y = int(line_ys[0]), int(line_ys[1]), int(line_ys[-1])

    xs = [left_x] + sorted(inner_xs)[:2] + [right_x]
    xs = merge_close_values(xs, 8)
    rows_n = 2
    cols_n = len(xs) - 1
    if cols_n not in (2, 3):
        return []

    cells = []
    for r in range(rows_n):
        cy1 = [top_y, middle_y][r]
        cy2 = [middle_y, bottom_y][r]
        for c in range(cols_n):
            cx1 = xs[c]
            cx2 = xs[c + 1]
            cells.append((int(x0 + cx1), int(y0 + cy1), int(x0 + cx2), int(y0 + cy2)))

    return cells
