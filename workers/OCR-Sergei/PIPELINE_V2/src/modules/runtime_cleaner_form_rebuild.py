from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.modules.runtime_cleaner_layout import build_axis_masks, extract_h_segments, extract_v_segments
from src.modules.runtime_cleaner_page_objects import build_page_ocr_json, merge_close_values
from src.modules.runtime_cleaner_stage1 import prepare_binary_mask

DPI = 200

from src.modules.runtime_cleaner_form_segments import (
    detect_form_closed_regions,
    _mm_to_px,
    merge_nearby_h_segments,
    merge_nearby_v_segments,
    extract_form_geometry_segments,
    detect_header_form_rois_with_outer_rebuild,
    draw_form_geometry_overlay,
)

def _pick_outer_form_lines(
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    min_h_len: int = 60,
    min_v_len: int = 60,
) -> dict | None:
    """
    Берём самые крайние длинные линии формы:
    - top:    самая верхняя горизонталь
    - bottom: самая нижняя горизонталь
    - left:   самая левая вертикаль
    - right:  самая правая вертикаль
    """
    h_long = [(y, x1, x2) for (y, x1, x2) in h_segments if abs(x2 - x1) >= min_h_len]
    v_long = [(x, y1, y2) for (x, y1, y2) in v_segments if abs(y2 - y1) >= min_v_len]

    if not h_long or not v_long:
        return None

    top = min(h_long, key=lambda s: s[0])
    bottom = max(h_long, key=lambda s: s[0])
    left = min(v_long, key=lambda s: s[0])
    right = max(v_long, key=lambda s: s[0])

    return {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
    }

def _is_lower_right_local_form_hline(
    y: int,
    x1: int,
    x2: int,
    outer_rect: tuple[int, int, int, int] | None,
    short_ratio: float = 0.45,
    zone_x_ratio: float = 0.62,
    zone_y_ratio: float = 0.72,
) -> bool:
    if outer_rect is None:
        return False

    left_x, top_y, right_x, bottom_y = map(int, outer_rect)
    form_w = max(1, right_x - left_x)
    form_h = max(1, bottom_y - top_y)
    line_len = max(1, x2 - x1)

    short_threshold = max(60, int(form_w * short_ratio))
    zone_x = left_x + int(form_w * zone_x_ratio)
    zone_y = top_y + int(form_h * zone_y_ratio)

    return line_len <= short_threshold and x1 >= zone_x and y >= zone_y

def extend_horizontal_segments_to_outer_verticals(
    h_segments,
    picked,
    outer_rect: tuple[int, int, int, int] | None = None,
) -> list[tuple[int, int, int]]:
    if picked is None:
        return h_segments

    left_x = int(picked["left"][0])
    right_x = int(picked["right"][0])

    out = []

    for y, x1, x2 in h_segments:
        y = int(y)
        x1 = int(x1)
        x2 = int(x2)

        if _is_lower_right_local_form_hline(y, x1, x2, outer_rect):
            out.append((y, x1, x2))
            continue

        out.append((y, left_x, right_x))

    return out



def _build_outer_rect_from_picked_lines(
    picked: dict | None,
    shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    """
    По 4 крайним линиям строим внешний прямоугольник:
    линии мысленно тянутся до пересечений,
    но в итоговый overlay рисуется только прямоугольник.
    """
    if picked is None:
        return None

    H, W = shape[:2]

    top_y = int(picked["top"][0])
    bottom_y = int(picked["bottom"][0])
    left_x = int(picked["left"][0])
    right_x = int(picked["right"][0])

    left_x = max(0, min(W - 1, left_x))
    right_x = max(0, min(W - 1, right_x))
    top_y = max(0, min(H - 1, top_y))
    bottom_y = max(0, min(H - 1, bottom_y))

    if right_x <= left_x or bottom_y <= top_y:
        return None

    return (left_x, top_y, right_x, bottom_y)


def _draw_outer_rect_on_overlay(
    overlay: np.ndarray,
    rect: tuple[int, int, int, int] | None,
    color: tuple[int, int, int] = (0, 0, 255),
    thickness: int = 2,
) -> np.ndarray:
    out = overlay.copy()

    if rect is None:
        return out

    x1, y1, x2, y2 = rect

    cv2.line(out, (x1, y1), (x2, y1), color, thickness)
    cv2.line(out, (x1, y2), (x2, y2), color, thickness)
    cv2.line(out, (x1, y1), (x1, y2), color, thickness)
    cv2.line(out, (x2, y1), (x2, y2), color, thickness)

    return out
