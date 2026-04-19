from __future__ import annotations

from src.modules.runtime_roi_assignment_common import clean_text, intersect_len


def build_box_lines_from_ocr(ocr_items, box_bbox, y_tol=14):
    bx1, by1, bx2, by2 = box_bbox

    box_items = []
    for item in ocr_items:
        x1, y1, x2, y2 = item["bbox"]

        if intersect_len(y1, y2, by1, by2) <= 0:
            continue
        if intersect_len(x1, x2, bx1, bx2) <= 0:
            continue

        text = clean_text(item.get("text"))
        if not text:
            continue

        box_items.append({"text": text, "bbox": item["bbox"]})

    box_items.sort(key=lambda it: (it["bbox"][1], it["bbox"][0]))

    lines = []
    for item in box_items:
        y = item["bbox"][1]
        placed = False
        for line in lines:
            if abs(y - line["y"]) <= y_tol:
                line["parts"].append(item)
                line["y_values"].append(y)
                placed = True
                break

        if not placed:
            lines.append({"y": y, "parts": [item], "y_values": [y]})

    out = []
    for line in lines:
        parts = sorted(line["parts"], key=lambda it: it["bbox"][0])
        text = clean_text(" ".join(p["text"] for p in parts if clean_text(p["text"])))
        if text:
            out.append({"y": int(round(sum(line["y_values"]) / len(line["y_values"]))), "text": text})
    return out
