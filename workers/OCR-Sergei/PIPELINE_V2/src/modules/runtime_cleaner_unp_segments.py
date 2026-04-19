from __future__ import annotations

import cv2
import numpy as np

from src.modules.runtime_cleaner_layout import extract_h_segments, extract_v_segments


def _cm_to_px(cm: float, dpi: int) -> int:
    return max(1, int(round(cm * dpi / 2.54)))

def _extract_axis_segments_for_unp(binary: np.ndarray) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """
    Из бинарной ROI-маски достаёт горизонтальные и вертикальные сегменты.
    Возвращает:
      h_segments: [(y, x1, x2), ...]
      v_segments: [(x, y1, y2), ...]
    """
    h_open = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1)),
    )
    v_open = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)),
    )

    h_segments = extract_h_segments(h_open, min_len=20)
    v_segments = extract_v_segments(v_open, min_len=20)
    return h_segments, v_segments

def _build_mask_from_segments(shape: tuple[int, int], h_segments, v_segments, thickness: int = 1) -> np.ndarray:
    out = np.zeros(shape, dtype=np.uint8)

    for y, x1, x2 in h_segments:
        cv2.line(out, (int(x1), int(y)), (int(x2), int(y)), 255, thickness)

    for x, y1, y2 in v_segments:
        cv2.line(out, (int(x), int(y1)), (int(x), int(y2)), 255, thickness)

    return out

def _segments_to_component_candidates(grid: np.ndarray):
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(grid, 8)
    candidates = []

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if area < 50:
            continue

        comp = (labels[y:y + h, x:x + w] == i).astype(np.uint8) * 255
        candidates.append({
            "bbox": (int(x), int(y), int(w), int(h)),
            "area": int(area),
            "mask": comp,
        })

    return candidates

def _analyze_unp_component(comp_mask: np.ndarray) -> dict | None:
    """
    Проверяет, можно ли считать компоненту UNP-блоком 2x2 / 2x3.
    Возвращает словарь с геометрией или None.
    """
    if comp_mask is None or comp_mask.size == 0:
        return None

    row_sum = (comp_mask > 0).sum(axis=1)
    col_sum = (comp_mask > 0).sum(axis=0)

    def merge_close(vals, tol=8):
        vals = sorted(int(v) for v in vals)
        if not vals:
            return []
        groups = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - groups[-1][-1]) <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [int(round(sum(g) / len(g))) for g in groups]

    h_, w_ = comp_mask.shape[:2]
    ys = merge_close(np.where(row_sum > max(10, int(w_ * 0.18)))[0], tol=8)
    xs = merge_close(np.where(col_sum > max(10, int(h_ * 0.18)))[0], tol=8)

    rows_n = len(ys) - 1
    cols_n = len(xs) - 1

    if rows_n == 2 and cols_n in (2, 3):
        return {
            "rows_n": rows_n,
            "cols_n": cols_n,
            "ys": ys,
            "xs": xs,
        }

    return None

def _clip_h_segment(seg, w: int, h: int):
    y, x1, x2 = seg
    y = max(0, min(h - 1, int(y)))
    x1 = max(0, min(w - 1, int(x1)))
    x2 = max(0, min(w - 1, int(x2)))
    if x2 < x1:
        x1, x2 = x2, x1
    return (y, x1, x2)

def _clip_v_segment(seg, w: int, h: int):
    x, y1, y2 = seg
    x = max(0, min(w - 1, int(x)))
    y1 = max(0, min(h - 1, int(y1)))
    y2 = max(0, min(h - 1, int(y2)))
    if y2 < y1:
        y1, y2 = y2, y1
    return (x, y1, y2)

def _extend_segments_stepwise(
    h_segments: list[tuple[int, int, int]],
    v_segments: list[tuple[int, int, int]],
    step_px: int,
    max_px: int,
    w: int,
    h: int,
):
    """
    Генерирует наборы сегментов:
    0 см, 0.5 см, 1.0 см, ... до 4 см.
    Горизонтали тянем влево/вправо.
    Вертикали тянем вверх/вниз.
    """
    yield h_segments, v_segments, 0

    steps = max_px // step_px
    for i in range(1, steps + 1):
        ext = i * step_px

        hs = []
        for y, x1, x2 in h_segments:
            hs.append(_clip_h_segment((y, x1 - ext, x2 + ext), w, h))

        vs = []
        for x, y1, y2 in v_segments:
            vs.append(_clip_v_segment((x, y1 - ext, y2 + ext), w, h))

        yield hs, vs, ext
