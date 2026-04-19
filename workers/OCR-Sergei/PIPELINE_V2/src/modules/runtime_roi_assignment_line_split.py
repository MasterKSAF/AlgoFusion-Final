from __future__ import annotations

from src.modules.runtime_roi_assignment_common import _bbox_area_for_ocr_target, clean_text, intersect_len


def split_line_by_rois(item, rois):
    x1, y1, x2, y2 = item["bbox"]
    text = str(item["text"]).strip()

    if not text:
        return []

    hits = []
    for roi in rois:
        rx1 = roi["bbox"]["x1"]
        rx2 = roi["bbox"]["x2"]
        ry1 = roi["bbox"]["y1"]
        ry2 = roi["bbox"]["y2"]

        y_overlap = intersect_len(y1, y2, ry1, ry2)
        if y_overlap <= 0:
            continue

        overlap = intersect_len(x1, x2, rx1, rx2)
        if overlap > 0:
            hits.append((roi, overlap))

    if not hits:
        return []

    if len(hits) == 1:
        return [(hits[0][0], text)]

    hits = sorted(hits, key=lambda x: x[0]["bbox"]["x1"])

    segments = []
    for roi, _ in hits:
        rx1 = roi["bbox"]["x1"]
        rx2 = roi["bbox"]["x2"]
        sx1 = max(x1, rx1)
        sx2 = min(x2, rx2)
        if sx2 > sx1:
            segments.append((roi, sx1, sx2))

    total_w = max(1, x2 - x1)
    words = text.split()
    n = len(words)

    result = []
    used = 0
    for i, (roi, sx1, sx2) in enumerate(segments):
        part_w = sx2 - sx1
        ratio = part_w / total_w
        take = round(ratio * n)

        if i == len(segments) - 1:
            chunk = words[used:]
        else:
            chunk = words[used : used + take]

        used += take
        part_text = " ".join(chunk).strip()
        if part_text:
            result.append((roi, part_text))

    return result


_split_line_by_rois_basic = split_line_by_rois


def split_line_by_order_form_rois(item, rois):
    form_rois = [roi for roi in rois if roi.get("kind") == "form_roi"]
    if not form_rois:
        return split_line_by_rois(item, rois)

    x1, y1, x2, y2 = item["bbox"]
    text = str(item["text"]).strip()
    if not text:
        return []

    y_mid = (y1 + y2) / 2
    hits = []
    for roi in form_rois:
        rx1 = roi["bbox"]["x1"]
        rx2 = roi["bbox"]["x2"]
        ry1 = roi["bbox"]["y1"]
        ry2 = roi["bbox"]["y2"]

        y_overlap = intersect_len(y1, y2, ry1, ry2)
        x_overlap = intersect_len(x1, x2, rx1, rx2)
        if y_overlap <= 0 or x_overlap <= 0:
            continue

        hits.append(
            {
                "roi": roi,
                "yo": y_overlap,
                "xo": x_overlap,
                "center_inside": ry1 <= y_mid <= ry2,
                "row_mid_delta": abs(((ry1 + ry2) / 2) - y_mid),
            }
        )

    if not hits:
        return []

    owner = max(
        hits,
        key=lambda hit: (
            1 if hit["center_inside"] else 0,
            hit["yo"],
            -hit["row_mid_delta"],
            hit["xo"],
        ),
    )
    owner_roi = owner["roi"]
    oy1 = owner_roi["bbox"]["y1"]
    oy2 = owner_roi["bbox"]["y2"]
    oh = max(1, oy2 - oy1)

    same_row = []
    for roi in form_rois:
        ry1 = roi["bbox"]["y1"]
        ry2 = roi["bbox"]["y2"]
        rh = max(1, ry2 - ry1)
        row_overlap = intersect_len(oy1, oy2, ry1, ry2)
        if row_overlap / max(1, min(oh, rh)) >= 0.80:
            same_row.append(roi)

    if not same_row:
        same_row = [owner_roi]

    return _split_line_by_rois_basic(item, sorted(same_row, key=lambda roi: roi["bbox"]["x1"]))

def split_line_by_rois_nested(item, rois):
    x1, y1, x2, y2 = item["bbox"]
    text = str(item["text"]).strip()

    if not text:
        return []

    hits = []
    for roi in rois:
        rx1 = roi["bbox"]["x1"]
        rx2 = roi["bbox"]["x2"]
        ry1 = roi["bbox"]["y1"]
        ry2 = roi["bbox"]["y2"]

        if intersect_len(y1, y2, ry1, ry2) <= 0:
            continue

        sx1 = max(x1, rx1)
        sx2 = min(x2, rx2)
        if sx2 <= sx1:
            continue

        hits.append(
            {
                "roi": roi,
                "sx1": sx1,
                "sx2": sx2,
                "area": _bbox_area_for_ocr_target(roi),
            }
        )

    needs_nested_priority = (
        any(hit["roi"].get("kind") == "header_box" for hit in hits)
        and any(hit["roi"].get("kind") in {"header_form_roi", "unp_cell"} for hit in hits)
    )
    if not needs_nested_priority:
        return _split_line_by_rois_basic(item, rois)

    if len(hits) == 1:
        return [(hits[0]["roi"], text)]

    cut_points = sorted({point for hit in hits for point in (hit["sx1"], hit["sx2"])})
    if len(cut_points) < 2:
        owner = min(hits, key=lambda hit: (hit["area"], hit["roi"]["bbox"]["x1"], hit["roi"]["bbox"]["y1"]))
        return [(owner["roi"], text)]

    owned_segments = []
    for left, right in zip(cut_points, cut_points[1:]):
        if right <= left:
            continue
        mid = (left + right) / 2
        owners = [hit for hit in hits if hit["sx1"] <= mid <= hit["sx2"]]
        if not owners:
            continue
        owner = min(owners, key=lambda hit: (hit["area"], hit["roi"]["bbox"]["x1"], hit["roi"]["bbox"]["y1"]))
        if owned_segments and owned_segments[-1][0]["id"] == owner["roi"]["id"]:
            prev_roi, prev_left, _ = owned_segments[-1]
            owned_segments[-1] = (prev_roi, prev_left, right)
        else:
            owned_segments.append((owner["roi"], left, right))

    total_w = max(1, x2 - x1)
    words = text.split()
    result = []
    used = 0

    for i, (roi, _sx1, sx2) in enumerate(owned_segments):
        if i == len(owned_segments) - 1:
            chunk = words[used:]
        else:
            next_used = round(((sx2 - x1) / total_w) * len(words))
            next_used = max(used, min(len(words), next_used))
            chunk = words[used:next_used]
            used = next_used

        part_text = " ".join(chunk).strip()
        if part_text:
            result.append((roi, part_text))

    return result
