from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.modules.runtime_cleaner_layout import build_axis_masks, extract_h_segments, extract_v_segments
from src.modules.runtime_cleaner_page_objects import build_page_ocr_json, merge_close_values
from src.modules.runtime_cleaner_stage1 import prepare_binary_mask

DPI = 200

def detect_form_closed_regions(
    mask: np.ndarray,
    h_segments: list[tuple[int,int,int]],
    v_segments: list[tuple[int,int,int]],
    outer_rect=None,
    min_area: int = 500,
):

    bin_img = prepare_binary_mask(mask)

    grid = np.zeros_like(bin_img)

    for y, x1, x2 in h_segments:
        cv2.line(grid, (int(x1), int(y)), (int(x2), int(y)), 255, 2)

    for x, y1, y2 in v_segments:
        cv2.line(grid, (int(x), int(y1)), (int(x), int(y2)), 255, 2)

    # добавляем внешний прямоугольник формы
    if outer_rect is not None:
        x1, y1, x2, y2 = map(int, outer_rect)

        cv2.line(grid, (x1, y1), (x2, y1), 255, 2)
        cv2.line(grid, (x1, y2), (x2, y2), 255, 2)
        cv2.line(grid, (x1, y1), (x1, y2), 255, 2)
        cv2.line(grid, (x2, y1), (x2, y2), 255, 2)

    grid = cv2.morphologyEx(
        grid,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (5,5)),
    )

    contours, hierarchy = cv2.findContours(
        grid,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    rois = []

    if hierarchy is None:
        return rois

    hierarchy = hierarchy[0]

    for i, cnt in enumerate(contours):

        x,y,w,h = cv2.boundingRect(cnt)

        if w*h < min_area:
            continue
        if w < 20 or h < 15:
            continue

        parent = hierarchy[i][3]
        if parent == -1:
            continue

        rois.append((int(x),int(y),int(x+w),int(y+h)))

    # удалить дубликаты
    uniq = []
    for box in sorted(rois):

        if not uniq:
            uniq.append(box)
            continue

        x1,y1,x2,y2 = box
        px1,py1,px2,py2 = uniq[-1]

        if (
            abs(x1-px1) <= 3 and
            abs(y1-py1) <= 3 and
            abs(x2-px2) <= 3 and
            abs(y2-py2) <= 3
        ):
            continue

        uniq.append(box)

    return uniq






def _mm_to_px(mm: float, dpi: int) -> int:
    return max(1, int(round(mm * dpi / 25.4)))


def merge_nearby_h_segments(
    h_segments: list[tuple[int, int, int]],
    axis_tol: int = 3,
    gap_tol: int = 16,
) -> list[tuple[int, int, int]]:
    """
    Склеивает горизонтали, если:
    - они почти на одной высоте
    - расстояние между ними по X маленькое
    """
    if not h_segments:
        return []

    rows = merge_close_values([y for y, _, _ in h_segments], axis_tol)
    grouped: dict[int, list[tuple[int, int]]] = {r: [] for r in rows}

    for y, x1, x2 in h_segments:
        r = min(rows, key=lambda rr: abs(rr - y))
        if abs(r - y) <= axis_tol:
            grouped[r].append((int(x1), int(x2)))

    merged: list[tuple[int, int, int]] = []

    for y in rows:
        parts = sorted(grouped[y])
        if not parts:
            continue

        cur_x1, cur_x2 = parts[0]
        for x1, x2 in parts[1:]:
            if x1 <= cur_x2 + gap_tol:
                cur_x2 = max(cur_x2, x2)
            else:
                merged.append((int(y), int(cur_x1), int(cur_x2)))
                cur_x1, cur_x2 = x1, x2

        merged.append((int(y), int(cur_x1), int(cur_x2)))

    return merged


def merge_nearby_v_segments(
    v_segments: list[tuple[int, int, int]],
    axis_tol: int = 3,
    gap_tol: int = 16,
) -> list[tuple[int, int, int]]:
    """
    Склеивает вертикали, если:
    - они почти на одном X
    - расстояние между ними по Y маленькое
    """
    if not v_segments:
        return []

    cols = merge_close_values([x for x, _, _ in v_segments], axis_tol)
    grouped: dict[int, list[tuple[int, int]]] = {c: [] for c in cols}

    for x, y1, y2 in v_segments:
        c = min(cols, key=lambda cc: abs(cc - x))
        if abs(c - x) <= axis_tol:
            grouped[c].append((int(y1), int(y2)))

    merged: list[tuple[int, int, int]] = []

    for x in cols:
        parts = sorted(grouped[x])
        if not parts:
            continue

        cur_y1, cur_y2 = parts[0]
        for y1, y2 in parts[1:]:
            if y1 <= cur_y2 + gap_tol:
                cur_y2 = max(cur_y2, y2)
            else:
                merged.append((int(x), int(cur_y1), int(cur_y2)))
                cur_y1, cur_y2 = y1, y2

        merged.append((int(x), int(cur_y1), int(cur_y2)))

    return merged


def extract_form_geometry_segments(
    mask: np.ndarray,
    dpi: int = 200,
    min_h_len: int = 30,
    min_v_len: int = 30,
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Для form-страницы:
    - берём только геометрические осевые линии
    - склеиваем близкие сегменты, если зазор <= 2 мм
    """
    bin_img = prepare_binary_mask(mask)
    hmask, vmask = build_axis_masks(bin_img)

    h_segments = extract_h_segments(hmask, min_len=min_h_len)
    v_segments = extract_v_segments(vmask, min_len=min_v_len)

    gap_tol = _mm_to_px(2.0, dpi)

    h_segments = merge_nearby_h_segments(
        h_segments,
        axis_tol=3,
        gap_tol=gap_tol,
    )
    v_segments = merge_nearby_v_segments(
        v_segments,
        axis_tol=3,
        gap_tol=gap_tol,
    )

    return h_segments, v_segments

def detect_header_form_rois_with_outer_rebuild(
    header_mask: np.ndarray,
    dpi: int = 200,
    min_h_len: int = 20,
    min_v_len: int = 20,
    min_area: int = 100,
    use_outer_rebuild: bool = False,
):
    h_segments_h, v_segments_h = extract_form_geometry_segments(
        header_mask,
        dpi=dpi,
        min_h_len=min_h_len,
        min_v_len=min_v_len,
    )

    seed_rois = detect_form_closed_regions(
        header_mask,
        h_segments_h,
        v_segments_h,
        min_area=min_area,
    )

    if not use_outer_rebuild or not seed_rois:
        return seed_rois

    picked = _pick_outer_form_lines(
        h_segments_h,
        v_segments_h,
        min_h_len=60,
        min_v_len=60,
    )

    outer_rect = _build_outer_rect_from_picked_lines(
        picked,
        shape=header_mask.shape,
    )

    if outer_rect is None:
        return seed_rois

    h_segments_ext = extend_horizontal_segments_to_outer_verticals(
        h_segments_h,
        picked,
        outer_rect=outer_rect,
    )

    rebuilt_rois = detect_form_closed_regions(
        header_mask,
        h_segments_ext,
        v_segments_h,
        outer_rect=outer_rect,
        min_area=min_area,
    )

    if len(rebuilt_rois) >= len(seed_rois):
        return rebuilt_rois

    return seed_rois


def draw_form_geometry_overlay(
    orig: np.ndarray,
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    color: tuple[int, int, int] = (0, 0, 255),
    thickness: int = 2,
) -> np.ndarray:
    out = orig.copy()

    for y, x1, x2 in h_segments:
        cv2.line(out, (int(x1), int(y)), (int(x2), int(y)), color, thickness)

    for x, y1, y2 in v_segments:
        cv2.line(out, (int(x), int(y1)), (int(x), int(y2)), color, thickness)

    return out
