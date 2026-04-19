from __future__ import annotations

import cv2
import numpy as np


def draw_page_signal_zones(clean_bgr: np.ndarray) -> np.ndarray:
    h, w = clean_bgr.shape[:2]
    page_overlay = clean_bgr.copy()
    zones = [
        ("top", 0, int(h * 0.28), (0, 180, 0)),
        ("mid", int(h * 0.28), int(h * 0.72), (0, 140, 255)),
        ("bot", int(h * 0.72), h, (255, 0, 0)),
    ]
    for label, y0, y1, color in zones:
        cv2.rectangle(page_overlay, (20, y0 + 5), (w - 20, y1 - 5), color, 2)
        cv2.putText(page_overlay, label, (28, min(h - 10, y0 + 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return page_overlay
