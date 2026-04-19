from __future__ import annotations

import numpy as np

def make_bbox(x1, y1, x2, y2):
    return {
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
        "w": int(x2 - x1),
        "h": int(y2 - y1),
    }


def clip_box_to_image(box, shape):
    x1, y1, x2, y2 = map(int, box)
    h, w = shape[:2]

    x1 = max(0, min(w - 1, x1))
    x2 = max(0, min(w - 1, x2))
    y1 = max(0, min(h - 1, y1))
    y2 = max(0, min(h - 1, y2))

    if x2 <= x1 or y2 <= y1:
        return None

    return (x1, y1, x2, y2)


def build_table_cells(rows, cols, image_shape, pad=6):
    rows = [int(v) for v in rows]
    cols = [int(v) for v in cols]

    cells = []
    cell_id = 1

    if len(rows) < 2 or len(cols) < 2:
        return cells

    for i in range(len(rows) - 1):
        for j in range(len(cols) - 1):
            x1 = cols[j] + pad
            y1 = rows[i] + pad
            x2 = cols[j + 1] - pad
            y2 = rows[i + 1] - pad

            clipped = clip_box_to_image((x1, y1, x2, y2), image_shape)
            if clipped is None:
                continue

            x1, y1, x2, y2 = clipped

            cells.append({
                "id": f"table_cell_{cell_id:04d}",
                "kind": "table_cell",
                "row": i + 1,
                "col": j + 1,
                "bbox": make_bbox(x1, y1, x2, y2),
            })
            cell_id += 1

    return cells


def build_overlay_objects_for_table(
    rows,
    cols,
    image_shape,
    header_box=None,
    footer_box=None,
    unp_cells=None,
    header_form_rois=None,
):
    objects = []
    rows = [int(v) for v in rows]
    cols = [int(v) for v in cols]
    unp_cells = unp_cells or []
    header_form_rois = header_form_rois or []

    if len(rows) >= 2 and len(cols) >= 2:
        x1 = int(min(cols))
        x2 = int(max(cols))
        y1 = int(min(rows))
        y2 = int(max(rows))

        for i, y in enumerate(rows, 1):
            objects.append({
                "id": f"grid_hline_{i:03d}",
                "kind": "grid_hline",
                "line": {
                    "x1": x1,
                    "y1": int(y),
                    "x2": x2,
                    "y2": int(y),
                }
            })

        for i, x in enumerate(cols, 1):
            objects.append({
                "id": f"grid_vline_{i:03d}",
                "kind": "grid_vline",
                "line": {
                    "x1": int(x),
                    "y1": y1,
                    "x2": int(x),
                    "y2": y2,
                }
            })

    if header_box is not None:
        clipped = clip_box_to_image(header_box, image_shape)
        if clipped is not None:
            objects.append({
                "id": "header_box",
                "kind": "header_box",
                "bbox": make_bbox(*clipped),
            })

    if footer_box is not None:
        clipped = clip_box_to_image(footer_box, image_shape)
        if clipped is not None:
            objects.append({
                "id": "footer_box",
                "kind": "footer_box",
                "bbox": make_bbox(*clipped),
            })

    for i, box in enumerate(unp_cells, 1):
        clipped = clip_box_to_image(box, image_shape)
        if clipped is None:
            continue

        objects.append({
            "id": f"unp_cell_{i:03d}",
            "kind": "unp_cell",
            "bbox": make_bbox(*clipped),
        })

    for i, box in enumerate(header_form_rois, 1):
        clipped = clip_box_to_image(box, image_shape)
        if clipped is None:
            continue

        objects.append({
            "id": f"header_form_roi_{i:04d}",
            "kind": "header_form_roi",
            "bbox": make_bbox(*clipped),
        })

    return objects


def build_overlay_objects_for_form(image_shape, outer_rect=None, form_rois=None):
    objects = []
    form_rois = form_rois or []

    if outer_rect is not None:
        clipped = clip_box_to_image(outer_rect, image_shape)
        if clipped is not None:
            objects.append({
                "id": "outer_rect",
                "kind": "form_outer_rect",
                "bbox": make_bbox(*clipped),
            })

    for i, box in enumerate(form_rois, 1):
        clipped = clip_box_to_image(box, image_shape)
        if clipped is None:
            continue
        objects.append({
            "id": f"form_roi_{i:04d}",
            "kind": "form_roi",
            "bbox": make_bbox(*clipped),
        })

    return objects


def build_page_ocr_json(
    page_id,
    layout,
    image_shape,
    rows=None,
    cols=None,
    header_box=None,
    footer_box=None,
    unp_cells=None,
    outer_rect=None,
    form_rois=None,
    header_form_rois=None,
    extra_meta=None,
):
    rows = rows or []
    cols = cols or []
    unp_cells = unp_cells or []
    form_rois = form_rois or []
    header_form_rois = header_form_rois or []
    extra_meta = extra_meta or {}

    h, w = image_shape[:2]
    page = {
        "page_id": page_id,
        "layout": str(layout),
        "image_size": {
            "width": int(w),
            "height": int(h),
        },
        "overlay_objects": [],
        "cells": [],
        "ocr_targets": [],
        "meta": extra_meta,
    }
    if layout == "table":
        table_cells = build_table_cells(rows, cols, image_shape=image_shape, pad=2)

        header_form_cells = []
        for i, box in enumerate(header_form_rois, 1):
            clipped = clip_box_to_image(box, image_shape)
            if clipped is None:
                continue

            header_form_cells.append({
                "id": f"header_form_roi_{i:04d}",
                "kind": "header_form_roi",
                "bbox": make_bbox(*clipped),
            })

        overlay_objects = build_overlay_objects_for_table(
            rows=rows,
            cols=cols,
            image_shape=image_shape,
            header_box=header_box,
            footer_box=footer_box,
            unp_cells=unp_cells,
            header_form_rois=header_form_rois,
        )

        special_targets = []

        if header_box is not None:
            clipped = clip_box_to_image(header_box, image_shape)
            if clipped is not None:
                special_targets.append({
                    "id": "header_box",
                    "kind": "header_box",
                    "bbox": make_bbox(*clipped),
                })

        if footer_box is not None:
            clipped = clip_box_to_image(footer_box, image_shape)
            if clipped is not None:
                special_targets.append({
                    "id": "footer_box",
                    "kind": "footer_box",
                    "bbox": make_bbox(*clipped),
                })

        for i, box in enumerate(unp_cells, 1):
            clipped = clip_box_to_image(box, image_shape)
            if clipped is None:
                continue

            special_targets.append({
                "id": f"unp_cell_{i:03d}",
                "kind": "unp_cell",
                "bbox": make_bbox(*clipped),
            })

        page["overlay_objects"] = overlay_objects
        page["cells"] = table_cells + header_form_cells
        page["ocr_targets"] = table_cells + header_form_cells + special_targets

    elif layout == "form":
        overlay_objects = build_overlay_objects_for_form(
            image_shape=image_shape,
            outer_rect=outer_rect,
            form_rois=form_rois,
        )

        form_cells = []
        for i, box in enumerate(form_rois, 1):
            clipped = clip_box_to_image(box, image_shape)
            if clipped is None:
                continue
            form_cells.append({
                "id": f"form_roi_{i:04d}",
                "kind": "form_roi",
                "bbox": make_bbox(*clipped),
            })

        page["overlay_objects"] = overlay_objects
        page["cells"] = form_cells
        page["ocr_targets"] = form_cells[:]

    return page

def extend_cols_with_page_boxes(
    cols: list[int],
    header_box=None,
    footer_box=None,
    min_extra_width: int = 120,
) -> list[int]:
    cols = [int(v) for v in cols]
    if not cols:
        return cols

    candidates = []

    if header_box is not None:
        candidates.append(int(header_box[2]))

    if footer_box is not None:
        candidates.append(int(footer_box[2]))

    if not candidates:
        return cols

    right_x = max(candidates)

    # если box уходит заметно правее последней найденной колонки,
    # считаем это правой границей последней колонки
    if right_x - cols[-1] >= min_extra_width:
        cols = merge_close_values(cols + [right_x], 3)

    return cols

def merge_close_values(vals: list[int], tol: int) -> list[int]:
    vals = sorted(vals)
    if not vals:
        return []

    groups = [[vals[0]]]
    for v in vals[1:]:
        if abs(v - groups[-1][-1]) <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])

    return [int(round(np.mean(g))) for g in groups]


def _to_str(v):
    if v is None:
        return ""
    return str(v).strip()


def is_index_row(texts):
    vals = [_to_str(v) for v in texts if _to_str(v) != ""]
    if len(vals) < 3:
        return False
    expected = [str(i) for i in range(1, len(vals) + 1)]
    return vals == expected


def is_header_row(texts):
    joined = " ".join(_to_str(t).lower() for t in texts)
    return any(w in joined for w in [
        "артикул", "товар", "штрих",
        "цена", "сумма", "ндс",
        "кол", "кол-во", "количество",
        "ед", "ед."
    ])


def is_total_row(texts):
    joined = " ".join(_to_str(t).lower() for t in texts)
    return "итого" in joined


def filter_table_rows(table_rows):
    clean_rows = []

    for row in table_rows:
        texts = [cell.get("text", "") for cell in row]

        if is_header_row(texts):
            continue
        if is_index_row(texts):
            continue
        if is_total_row(texts):
            continue

        clean_rows.append(row)

    return clean_rows


__all__ = [
    "build_overlay_objects_for_form",
    "build_overlay_objects_for_table",
    "build_page_ocr_json",
    "build_table_cells",
    "clip_box_to_image",
    "extend_cols_with_page_boxes",
    "filter_table_rows",
    "is_header_row",
    "is_index_row",
    "is_total_row",
    "make_bbox",
    "merge_close_values",
]
