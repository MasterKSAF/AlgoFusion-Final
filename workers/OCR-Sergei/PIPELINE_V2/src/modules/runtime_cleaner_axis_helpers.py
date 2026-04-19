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

def extract_rows_cols_from_grid_mask(grid_mask: np.ndarray):
    bin_img = (grid_mask > 0).astype(np.uint8) * 255

    h_segments = extract_h_segments(bin_img, min_len=20)
    v_segments = extract_v_segments(bin_img, min_len=20)

    rows = merge_close_values([y for y, _, _ in h_segments], 3)
    cols = merge_close_values([x for x, _, _ in v_segments], 3)

    return rows, cols








def build_axis_masks(binary: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (H_OPEN, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, V_OPEN))

    hmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, hk)
    vmask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vk)

    h_close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (H_CLOSE, 1))
    v_close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, V_CLOSE))

    hmask = cv2.morphologyEx(hmask, cv2.MORPH_CLOSE, h_close_kernel)
    vmask = cv2.morphologyEx(vmask, cv2.MORPH_CLOSE, v_close_kernel)

    return hmask, vmask


def build_table_axis_masks(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Общая подготовка mask для table-логики.
    Возвращает:
    - bin_img
    - hmask
    - vmask (уже с доп. close 1x11)
    """
    bin_img = prepare_binary_mask(mask)
    hmask, vmask = build_axis_masks(bin_img)
    vmask = cv2.morphologyEx(
        vmask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, 11)),
    )
    return bin_img, hmask, vmask


def extract_h_segments(binary: np.ndarray, min_len: int) -> list[tuple[int, int, int]]:
    segs: list[tuple[int, int, int]] = []
    h, _ = binary.shape

    for y in range(h):
        xs = np.where(binary[y] > 0)[0]
        if len(xs) == 0:
            continue

        start = prev = int(xs[0])

        for x in xs[1:]:
            x = int(x)
            if x == prev + 1:
                prev = x
            else:
                if prev - start + 1 >= min_len:
                    segs.append((y, start, prev))
                start = prev = x

        if prev - start + 1 >= min_len:
            segs.append((y, start, prev))

    return segs


def extract_v_segments(binary: np.ndarray, min_len: int) -> list[tuple[int, int, int]]:
    segs: list[tuple[int, int, int]] = []
    _, w = binary.shape

    for x in range(w):
        ys = np.where(binary[:, x] > 0)[0]
        if len(ys) == 0:
            continue

        start = prev = int(ys[0])

        for y in ys[1:]:
            y = int(y)
            if y == prev + 1:
                prev = y
            else:
                if prev - start + 1 >= min_len:
                    segs.append((x, start, prev))
                start = prev = y

        if prev - start + 1 >= min_len:
            segs.append((x, start, prev))

    return segs


def row_vertical_support(row_y: int, v_segments: list[tuple[int, int, int]], x0: int, x1: int, band: int = 2) -> int:
    cnt = 0
    for x, y1, y2 in v_segments:
        if x0 <= x <= x1 and (y1 - band) <= row_y <= (y2 + band):
            cnt += 1
    return cnt


def col_horizontal_support(col_x: int, h_segments: list[tuple[int, int, int]], y0: int, y1: int, band: int = 2) -> int:
    cnt = 0
    for y, x1, x2 in h_segments:
        if y0 <= y <= y1 and (x1 - band) <= col_x <= (x2 + band):
            cnt += 1
    return cnt


def vertical_coverage(col_x: int, v_segments: list[tuple[int, int, int]], y0: int, y1: int, band: int = 3) -> float:
    spans: list[tuple[int, int]] = []

    for x, ya, yb in v_segments:
        if abs(x - col_x) <= band:
            a = max(ya, y0)
            b = min(yb, y1)
            if a <= b:
                spans.append((a, b))

    if not spans:
        return 0.0

    spans.sort()
    merged = [list(spans[0])]

    for a, b in spans[1:]:
        if a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    covered = sum(b - a + 1 for a, b in merged)
    total = max(1, y1 - y0 + 1)
    return covered / total


def count_intersections(h_segments: list[tuple[int, int, int]], v_segments: list[tuple[int, int, int]], band: int = 2) -> int:
    intersections = 0
    for y, x1, x2 in h_segments:
        for x, y1, y2 in v_segments:
            if (x1 - band) <= x <= (x2 + band) and (y1 - band) <= y <= (y2 + band):
                intersections += 1
    return intersections
