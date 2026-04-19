from __future__ import annotations

import cv2
import numpy as np


def remove_lines(orig, mask):
    mask = (mask > 0).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.inpaint(orig, mask, 3, cv2.INPAINT_TELEA)


def expand_box(x1, y1, x2, y2, w, h, pad=2):
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)
    return x1, y1, x2, y2


def draw_rois_on_clean(clean_bgr, roi_items):
    out = clean_bgr.copy()
    h, w = out.shape[:2]

    color_map = {
        "table_cell": (0, 0, 255),
        "header_box": (180, 0, 180),
        "header_form_roi": (180, 0, 180),
        "footer_box": (255, 0, 0),
        "unp_cell": (0, 165, 255),
        "form_outer_rect": (180, 0, 180),
        "outer_rect": (180, 0, 180),
        "form_roi": (180, 0, 180),
        "roi": (180, 0, 180),
    }
    font = cv2.FONT_HERSHEY_SIMPLEX

    for item in roi_items:
        kind = item.get("kind", "roi")
        bbox = item["bbox"]
        x1, y1, x2, y2 = expand_box(
            int(bbox["x1"]),
            int(bbox["y1"]),
            int(bbox["x2"]),
            int(bbox["y2"]),
            w=w,
            h=h,
            pad=2,
        )
        color = color_map.get(kind, (180, 0, 180))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)

        label = str(item.get("id", "")).split("_")[-1]
        tx = x1 + 3
        ty = y1 + 13
        (tw, th), _ = cv2.getTextSize(label, font, 0.4, 1)

        cv2.rectangle(
            out,
            (tx - 2, ty - th - 2),
            (tx + tw + 2, ty + 3),
            (255, 255, 255),
            -1,
        )
        cv2.putText(
            out,
            label,
            (tx, ty),
            font,
            0.4,
            color,
            1,
            cv2.LINE_AA,
        )

    return out
