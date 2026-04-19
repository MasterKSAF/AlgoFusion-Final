from __future__ import annotations

import json
import os

from src.modules.runtime_roi_assignment_helpers import (
    _group_waybill_table_rows,
    _waybill_fix_table_row_cells,
    build_box_lines_from_ocr,
    clean_text,
    split_line_by_order_form_rois,
    split_line_by_rois_nested,
    split_line_by_waybill_table_rois,
)

def run_roi_assignment_pipeline(clean_png, roi_json, raw_ocr_json):
    with open(roi_json, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    with open(raw_ocr_json, "r", encoding="utf-8") as handle:
        raw_ocr_data = json.load(handle)

    ocr_items = raw_ocr_data.get("ocr_items", [])
    rois = data.get("ocr_targets", data.get("rois", []))
    page_id_lc = str(data.get("page_id", "")).lower()

    rois_sorted = sorted(rois, key=lambda roi: (roi["bbox"]["x2"] - roi["bbox"]["x1"]) * (roi["bbox"]["y2"] - roi["bbox"]["y1"]))
    roi_texts = {roi["id"]: [] for roi in rois_sorted}

    route_splitter = split_line_by_rois_nested
    if ("order" in page_id_lc or "payment_order" in page_id_lc) and any(roi.get("kind") == "form_roi" for roi in rois_sorted):
        route_splitter = split_line_by_order_form_rois
    elif "waybill" in page_id_lc and any(roi.get("kind") == "table_cell" for roi in rois_sorted):
        route_splitter = split_line_by_waybill_table_rois

    for item in ocr_items:
        parts = route_splitter(item, rois_sorted)
        for roi, part in parts:
            if part:
                roi_texts[roi["id"]].append(part)

    if "waybill" in page_id_lc:
        table_rois = [roi for roi in rois_sorted if roi.get("kind") == "table_cell"]
        grouped_rows = _group_waybill_table_rows(table_rois)
        rows_map = {idx: row["rois"] for idx, row in enumerate(grouped_rows)}

        def _roi_height(roi):
            bbox = roi.get("bbox", {})
            return max(0, int(bbox.get("y2", 0)) - int(bbox.get("y1", 0)))

        def _is_pure_col_index_text(text, col):
            cleaned = clean_text(text)
            return bool(cleaned) and cleaned == str(col)

        def _looks_like_waybill_index_row(row_rois):
            if not row_rois:
                return False

            row_rois = sorted(row_rois, key=lambda r: (r.get("col") or 0))
            matched = 0
            nonempty = 0
            heights = []
            single_digit_cells = 0
            first_cols_emptyish = 0

            for idx, roi in enumerate(row_rois):
                rid = roi["id"]
                col = roi.get("col")
                txt = clean_text(" ".join(roi_texts.get(rid, [])))
                heights.append(_roi_height(roi))

                if idx < 3 and (not txt or _is_pure_col_index_text(txt, col)):
                    first_cols_emptyish += 1

                if not txt:
                    continue

                nonempty += 1
                if _is_pure_col_index_text(txt, col):
                    matched += 1
                    single_digit_cells += 1

            if nonempty < 5:
                return False

            numeric_ratio_ok = matched >= 5 and matched / max(nonempty, 1) >= 0.6
            heights = [h for h in heights if h > 0]
            if not heights:
                return False

            row_h = min(heights)
            other_row_heights = []
            for other_rois in rows_map.values():
                if other_rois is row_rois:
                    continue
                hs = [_roi_height(r) for r in other_rois if _roi_height(r) > 0]
                if hs:
                    other_row_heights.append(min(hs))

            if not other_row_heights:
                return numeric_ratio_ok

            median_other_h = sorted(other_row_heights)[len(other_row_heights) // 2]
            height_ratio_ok = row_h <= max(18, int(median_other_h * 0.60))
            digit_ratio_ok = single_digit_cells >= max(4, (len(row_rois) + 1) // 2)
            first_cols_ok = first_cols_emptyish >= 2
            return numeric_ratio_ok and height_ratio_ok and (first_cols_ok or digit_ratio_ok)

        index_row_num = None
        for row_num in sorted(rows_map):
            if _looks_like_waybill_index_row(rows_map[row_num]):
                index_row_num = row_num
                break

        if index_row_num is not None:
            next_row_num = index_row_num + 1
            next_row_by_col = {roi.get("col"): roi for roi in rows_map.get(next_row_num, [])}

            for roi in rows_map[index_row_num]:
                rid = roi["id"]
                col = roi.get("col")
                raw_text = clean_text(" ".join(roi_texts.get(rid, [])))

                if not raw_text or not _is_pure_col_index_text(raw_text, col):
                    continue

                target_roi = next_row_by_col.get(col)
                if target_roi is None:
                    continue

                target_id = target_roi["id"]
                roi_texts[target_id] = [raw_text] + roi_texts.get(target_id, [])
                roi_texts[rid] = []

        _waybill_fix_table_row_cells(grouped_rows, roi_texts, ocr_items=ocr_items)

    regions_raw = []
    for roi in rois_sorted:
        rb = [
            roi["bbox"]["x1"],
            roi["bbox"]["y1"],
            roi["bbox"]["x2"],
            roi["bbox"]["y2"],
        ]
        text = " ".join(roi_texts[roi["id"]]).strip()
        region_obj = {
            "id": roi["id"],
            "kind": roi.get("kind", "unknown"),
            "bbox": rb,
            "text": text,
        }
        if roi["id"] == "header_box":
            region_obj["header_lines"] = build_box_lines_from_ocr(ocr_items, rb)
        if roi["id"] == "footer_box":
            region_obj["footer_lines"] = build_box_lines_from_ocr(ocr_items, rb)
        regions_raw.append(region_obj)

    step = 20
    regions_sorted = sorted(regions_raw, key=lambda r: (round(r["bbox"][1] / step), r["bbox"][0]))
    html_blocks = []
    for region in regions_sorted:
        if region["text"]:
            html_blocks.append(
                f"<div class='roi'><h3>{region['id']} ({region['kind']})</h3><p>{region['text']}</p></div>"
            )

    out_json = {
        "page_id": data.get("page_id", os.path.basename(clean_png)),
        "regions": regions_sorted,
    }
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>OCR ROI: {os.path.basename(clean_png)}</title>
<style>
body {{ font-family: Arial, sans-serif; line-height: 1.5; padding: 20px; }}
.roi {{ border: 1px solid #aaa; padding: 10px; margin: 10px 0; border-radius: 5px; }}
.roi h3 {{ margin: 0 0 5px 0; font-size: 1.1em; color: #333; }}
.roi p {{ margin: 0; }}
</style>
</head>
<body>
<h1>Page: {os.path.basename(clean_png)}</h1>
{''.join(html_blocks)}
</body>
</html>"""

    out_json_path = os.path.join(
        os.path.dirname(clean_png),
        f"{os.path.basename(clean_png).replace('__clean.png', '')}_roi_text.json",
    )
    with open(out_json_path, "w", encoding="utf-8") as handle:
        json.dump(out_json, handle, ensure_ascii=False, indent=2)

    out_html_path = os.path.join(
        os.path.dirname(clean_png),
        f"{os.path.basename(clean_png).replace('__clean.png', '')}_roi_text.html",
    )
    with open(out_html_path, "w", encoding="utf-8") as handle:
        handle.write(html_content)

    print(f"ROI text saved: {out_json_path}")
    return out_json, html_content
