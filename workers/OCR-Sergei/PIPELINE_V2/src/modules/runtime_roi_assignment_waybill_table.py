from __future__ import annotations

import re

from src.modules.runtime_roi_assignment_common import clean_text, intersect_len
from src.modules.runtime_roi_assignment_line_split import split_line_by_rois, split_line_by_rois_nested


def _group_waybill_table_rows(table_rois):
    rows = []
    for roi in sorted(table_rois, key=lambda r: (r["bbox"]["y1"], r["bbox"]["x1"])):
        bbox = roi["bbox"]
        y1 = bbox["y1"]
        y2 = bbox["y2"]
        height = max(1, y2 - y1)
        cy = (y1 + y2) / 2

        best = None
        best_key = None
        for row in rows:
            dy1 = abs(y1 - row["y1"])
            dy2 = abs(y2 - row["y2"])
            dcy = abs(cy - row["cy"])
            dh = abs(height - row["h"])
            same_band = (dy1 <= 4 and dy2 <= 4) or (dcy <= 4 and dh <= 6)
            if not same_band:
                continue
            key = (dy1 + dy2, dcy, dh, abs(bbox["x1"] - row["min_x1"]))
            if best_key is None or key < best_key:
                best = row
                best_key = key

        if best is None:
            rows.append(
                {
                    "y1": y1,
                    "y2": y2,
                    "cy": cy,
                    "h": height,
                    "min_x1": bbox["x1"],
                    "rois": [roi],
                }
            )
        else:
            count = len(best["rois"])
            best["y1"] = (best["y1"] * count + y1) / (count + 1)
            best["y2"] = (best["y2"] * count + y2) / (count + 1)
            best["cy"] = (best["cy"] * count + cy) / (count + 1)
            best["h"] = (best["h"] * count + height) / (count + 1)
            best["min_x1"] = min(best["min_x1"], bbox["x1"])
            best["rois"].append(roi)

    for row in rows:
        row["rois"] = sorted(row["rois"], key=lambda r: r["bbox"]["x1"])
        row["y1"] = min(r["bbox"]["y1"] for r in row["rois"])
        row["y2"] = max(r["bbox"]["y2"] for r in row["rois"])
        row["cy"] = (row["y1"] + row["y2"]) / 2
        row["h"] = max(1, row["y2"] - row["y1"])
    return rows

def _split_waybill_leading_amount(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None, None

    match = re.match(r"^\s*(\d+[.,]\d{2})\s+(.+?)\s*$", cleaned)
    if not match:
        return None, None

    lead = clean_text(match.group(1))
    tail = clean_text(match.group(2))
    if not lead or not tail:
        return None, None

    return lead, tail

def split_line_by_waybill_table_rois(item, rois):
    table_rois = [roi for roi in rois if roi.get("kind") == "table_cell"]
    if not table_rois:
        return split_line_by_rois_nested(item, rois)

    x1, y1, x2, y2 = item["bbox"]
    text = str(item.get("text", "")).strip()
    if not text:
        return []

    y_mid = (y1 + y2) / 2
    rows = _group_waybill_table_rows(table_rois)

    row_hits = []
    for row in rows:
        row_overlap = intersect_len(y1, y2, row["y1"], row["y2"])
        if row_overlap <= 0:
            continue
        row_hits.append(
            {
                "row": row,
                "yo": row_overlap,
                "center_inside": row["y1"] <= y_mid <= row["y2"],
                "row_mid_delta": abs(row["cy"] - y_mid),
            }
        )

    if not row_hits:
        other_rois = [roi for roi in rois if roi.get("kind") != "table_cell"]
        if not other_rois:
            return []
        # For header regions we must preserve nested priority:
        # smaller UNP/header form boxes should win over the coarse header_box.
        return split_line_by_rois_nested(item, other_rois)

    owner_row = max(
        row_hits,
        key=lambda hit: (
            1 if hit["center_inside"] else 0,
            hit["yo"],
            -hit["row_mid_delta"],
        ),
    )["row"]

    cell_hits = []
    for roi in owner_row["rois"]:
        rx1 = roi["bbox"]["x1"]
        rx2 = roi["bbox"]["x2"]
        x_overlap = intersect_len(x1, x2, rx1, rx2)
        if x_overlap <= 0:
            continue
        cell_hits.append({"roi": roi, "xo": x_overlap})

    if not cell_hits:
        return []

    if len(cell_hits) == 1:
        return [(cell_hits[0]["roi"], clean_text(text))]

    cell_hits = sorted(cell_hits, key=lambda hit: hit["roi"]["bbox"]["x1"])

    if len(cell_hits) == 2:
        left_hit, right_hit = cell_hits
        left_box = left_hit["roi"]["bbox"]
        right_box = right_hit["roi"]["bbox"]
        left_w = max(1, left_box["x2"] - left_box["x1"])
        right_w = max(1, right_box["x2"] - right_box["x1"])
        lead, tail = _split_waybill_leading_amount(text)
        if lead and tail and left_w <= 160 and right_w >= 250 and right_box["x1"] > left_box["x1"]:
            return [(left_hit["roi"], lead), (right_hit["roi"], tail)]

    item_w = max(1, x2 - x1)
    owner = max(
        cell_hits,
        key=lambda hit: (
            hit["xo"] / item_w,
            -hit["roi"]["bbox"]["x1"],
        ),
    )
    return [(owner["roi"], clean_text(text))]

def _strip_waybill_table_markup(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    cleaned = re.sub(r"<\s*br\s*/?\s*>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"</?(?:b|u|i|em|strong|span|div|p)[^>]*>", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return clean_text(cleaned)

def _split_waybill_ocr_visual_lines(item):
    text = str(item.get("text", "") or "")
    bbox = item.get("bbox") or [0, 0, 0, 0]
    x1, y1, x2, y2 = bbox
    pieces = re.split(r"<\s*br\s*/?\s*>|\n+", text, flags=re.I)
    pieces = [
        clean_text(re.sub(r"</?(?:b|u|i|em|strong|span|div|p)[^>]*>", " ", piece, flags=re.I))
        for piece in pieces
    ]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return []

    total_h = max(1, y2 - y1)
    part_h = total_h / max(1, len(pieces))
    out = []
    for i, piece in enumerate(pieces):
        py1 = y1 + part_h * i
        py2 = y2 if i == len(pieces) - 1 else y1 + part_h * (i + 1)
        out.append({"text": piece, "bbox": [x1, py1, x2, py2]})
    return out

def _repair_waybill_name_column_from_raw(grouped_rows, roi_texts, ocr_items):
    if not grouped_rows or not ocr_items:
        return

    grouped_rows = sorted(grouped_rows, key=lambda row: row["y1"])
    name_entries = []
    for idx, row in enumerate(grouped_rows):
        row_rois = sorted(row["rois"], key=lambda r: r["bbox"]["x1"])
        if not row_rois:
            continue
        name_roi = row_rois[0]
        name_w = name_roi["bbox"]["x2"] - name_roi["bbox"]["x1"]
        if name_w < 180 or idx < 2:
            continue
        name_entries.append(
            {
                "roi": name_roi,
                "y1": name_roi["bbox"]["y1"],
                "y2": name_roi["bbox"]["y2"],
                "cy": (name_roi["bbox"]["y1"] + name_roi["bbox"]["y2"]) / 2,
            }
        )

    if not name_entries:
        return

    for entry in name_entries:
        roi_texts[entry["roi"]["id"]] = []

    for item in ocr_items:
        for piece in _split_waybill_ocr_visual_lines(item):
            text = piece["text"]
            x1, y1, x2, y2 = piece["bbox"]
            cy = (y1 + y2) / 2
            candidates = []
            for entry in name_entries:
                roi = entry["roi"]
                rx1 = roi["bbox"]["x1"]
                ry1 = roi["bbox"]["y1"]
                rx2 = roi["bbox"]["x2"]
                ry2 = roi["bbox"]["y2"]
                x_overlap = intersect_len(x1, x2, rx1, rx2)
                y_overlap = intersect_len(y1, y2, ry1, ry2)
                if x_overlap <= 0 or y_overlap <= 0:
                    continue
                candidates.append(
                    {
                        "entry": entry,
                        "x_overlap": x_overlap,
                        "y_overlap": y_overlap,
                        "center_inside": ry1 <= cy <= ry2,
                        "cy_delta": abs(entry["cy"] - cy),
                    }
                )

            if not candidates:
                continue

            owner = max(
                candidates,
                key=lambda hit: (
                    1 if hit["center_inside"] else 0,
                    hit["y_overlap"],
                    hit["x_overlap"],
                    -hit["cy_delta"],
                ),
            )["entry"]
            roi_texts[owner["roi"]["id"]].append(text)

def _waybill_fix_table_row_cells(grouped_rows, roi_texts, ocr_items=None):
    _repair_waybill_name_column_from_raw(grouped_rows, roi_texts, ocr_items)

    for row in grouped_rows:
        for roi in row["rois"]:
            rid = roi["id"]
            cleaned_parts = []
            for part in roi_texts.get(rid, []):
                cleaned = _strip_waybill_table_markup(part)
                if cleaned:
                    cleaned_parts.append(cleaned)
            roi_texts[rid] = cleaned_parts
