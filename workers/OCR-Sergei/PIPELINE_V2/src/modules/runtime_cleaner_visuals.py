from __future__ import annotations

import cv2
import numpy as np

from src.modules.runtime_cleaner_unp import _cm_to_px

def _mm_to_px(mm: float, dpi: int) -> int:
    return max(1, int(round(mm * dpi / 25.4)))

def build_form_overlay_mask(mask: np.ndarray) -> np.ndarray:
    out = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
    )
    out = cv2.dilate(
        out,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
        iterations=1,
    )
    return out


def build_form_mask_above_table(mask: np.ndarray, table_top_y: int) -> np.ndarray:
    """
    Всё выше основной таблицы считаем формой.
    """
    form_mask = np.zeros_like(mask)
    if table_top_y <= 0:
        return form_mask

    form_mask[:table_top_y, :] = mask[:table_top_y, :]
    return form_mask




def make_overlay(orig_bgr: np.ndarray, grid_mask: np.ndarray) -> np.ndarray:
    out = orig_bgr.copy()
    ys, xs = np.where(grid_mask > 0)
    out[ys, xs] = (0, 0, 255)
    return out


def make_overlay_two_colors(orig_bgr: np.ndarray, red_mask: np.ndarray | None = None, green_mask: np.ndarray | None = None) -> np.ndarray:
    out = orig_bgr.copy()

    if green_mask is not None:
        ys, xs = np.where(green_mask > 0)
        out[ys, xs] = (0, 255, 0)

    if red_mask is not None:
        ys, xs = np.where(red_mask > 0)
        out[ys, xs] = (0, 0, 255)

    return out

def detect_header_last_text_y(orig_bgr: np.ndarray, y1: int) -> int:
    h, w = orig_bgr.shape[:2]
    y1 = max(1, min(h, int(y1)))

    roi = orig_bgr[0:y1]
    if roi.size == 0:
        return 0

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15,
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (12, 3)),
    )

    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    last_y = 0
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)

        if ww < 10 or hh < 6:
            continue
        if ww * hh < 80:
            continue

        last_y = max(last_y, y + hh)

    return last_y

def detect_footer_last_text_y(orig_bgr: np.ndarray, y0: int) -> int:
    h, w = orig_bgr.shape[:2]
    y0 = max(0, min(h - 1, int(y0)))

    roi = orig_bgr[y0:h]
    if roi.size == 0:
        return y0

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        15,
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)),
    )

    bw = cv2.morphologyEx(
        bw,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (12, 3)),
    )

    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    last_y = y0
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)

        if ww < 10 or hh < 6:
            continue
        if ww * hh < 80:
            continue

        last_y = max(last_y, y0 + y + hh)

    return last_y


def draw_footer_blue_box(
    overlay: np.ndarray,
    table_bottom_y: int,
    footer_bottom_y: int,
    dpi: int = 200,
) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    h, w = overlay.shape[:2]

    pad_x = _cm_to_px(0.5, dpi)
    pad_top = _mm_to_px(1.0, dpi)

    x1 = pad_x
    x2 = w - pad_x
    y1 = min(h - 1, table_bottom_y + pad_top)
    y2 = min(h - 1, footer_bottom_y)

    if y2 <= y1:
        return overlay, None

    out = overlay.copy()
    cv2.rectangle(out, (x1, y1), (x2, y2), (255, 0, 0), 3)
    return out, (x1, y1, x2, y2)

def draw_header_green_box(
    overlay: np.ndarray,
    header_bottom_y: int,
    dpi: int = 200,
) -> tuple[np.ndarray, tuple[int, int, int, int] | None]:
    h, w = overlay.shape[:2]

    pad_x = _cm_to_px(0.5, dpi)
    pad_bottom = _cm_to_px(0.3, dpi)

    x1 = pad_x
    x2 = w - pad_x
    y1 = _cm_to_px(0.5, dpi)
    y2 = min(h - 1, header_bottom_y + pad_bottom)

    if y2 <= y1:
        return overlay, None

    out = overlay.copy()
    cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 3)
    return out, (x1, y1, x2, y2)


# =========================================================
# ЭТАП 2 — ОБРАБОТКА СТРАНИЦ
# =========================================================


__all__ = [
    "build_form_mask_above_table",
    "build_form_overlay_mask",
    "detect_footer_last_text_y",
    "detect_header_last_text_y",
    "draw_footer_blue_box",
    "draw_header_green_box",
    "make_overlay",
    "make_overlay_two_colors",
]
