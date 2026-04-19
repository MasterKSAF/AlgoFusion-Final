from __future__ import annotations

import re


def intersect_len(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))

def clean_text(value):
    if value is None:
        return None
    value = str(value).replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value or None

def _bbox_area_for_ocr_target(roi):
    bbox = roi["bbox"]
    return max(0, bbox["x2"] - bbox["x1"]) * max(0, bbox["y2"] - bbox["y1"])
