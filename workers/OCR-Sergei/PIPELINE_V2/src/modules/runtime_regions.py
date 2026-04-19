from __future__ import annotations

from typing import Any

from src.modules.runtime_common import (
    region_bbox_xyxy as _region_bbox_xyxy,
    strip_ocr_markup as _strip_ocr_markup,
)
from src.modules.runtime_io import read_json as _read_json
from src.modules.runtime_text_quality import _clean_inline_text


def group_regions_by_rows(regions: list[dict[str, Any]], kind: str = "table_cell", tol: int = 14) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    selected = [region for region in regions if region.get("kind") == kind]
    for region in sorted(selected, key=lambda row: (_region_bbox_xyxy(row)[1], _region_bbox_xyxy(row)[0])):
        y1 = _region_bbox_xyxy(region)[1]
        placed = False
        for row in rows:
            avg_y = sum(_region_bbox_xyxy(item)[1] for item in row) / max(1, len(row))
            if abs(y1 - avg_y) <= tol:
                row.append(region)
                placed = True
                break
        if not placed:
            rows.append([region])
    for row in rows:
        row.sort(key=lambda item: _region_bbox_xyxy(item)[0])
    return rows


def row_texts(regions: list[dict[str, Any]]) -> list[str]:
    return [_clean_inline_text(region.get("text")) or "" for region in regions]


def row_join_text(regions: list[dict[str, Any]]) -> str:
    return _clean_inline_text(" ".join(row_texts(regions))) or ""


def group_ocr_lines(ocr_items: list[dict[str, Any]], y_tol: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in ocr_items or []:
        text = _strip_ocr_markup(item.get("text"))
        bbox = item.get("bbox") or [0, 0, 0, 0]
        if not text or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in bbox]
        yc = (y1 + y2) / 2.0
        placed = False
        for row in rows:
            if abs(row["yc"] - yc) <= y_tol:
                row["items"].append({"x1": x1, "text": text, "bbox": [x1, y1, x2, y2]})
                row["yc"] = (row["yc"] * row["n"] + yc) / (row["n"] + 1)
                row["n"] += 1
                placed = True
                break
        if not placed:
            rows.append({"yc": yc, "n": 1, "items": [{"x1": x1, "text": text, "bbox": [x1, y1, x2, y2]}]})
    rows.sort(key=lambda row: row["yc"])
    for row in rows:
        row["items"].sort(key=lambda cell: cell["x1"])
        row["text"] = _strip_ocr_markup(" ".join(cell["text"] for cell in row["items"]))
    return rows


def row_to_pipe_text(row: dict[str, Any]) -> str:
    cells = row.get("items") or []
    parts = [_strip_ocr_markup(cell.get("text")) for cell in cells if _strip_ocr_markup(cell.get("text"))]
    return " | ".join(parts)


def group_region_lines(
    regions: list[dict[str, Any]],
    *,
    kinds: set[str] | None = None,
    y_tol: int = 12,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in regions:
        if kinds and region.get("kind") not in kinds:
            continue
        text = _strip_ocr_markup(region.get("text"))
        bbox = _region_bbox_xyxy(region)
        if not text:
            continue
        x1, y1, x2, y2 = bbox
        yc = (y1 + y2) / 2.0
        placed = False
        for row in rows:
            if abs(row["yc"] - yc) <= y_tol:
                row["items"].append({"x1": x1, "text": text, "bbox": [x1, y1, x2, y2], "region": region})
                row["yc"] = (row["yc"] * row["n"] + yc) / (row["n"] + 1)
                row["n"] += 1
                placed = True
                break
        if not placed:
            rows.append(
                {
                    "yc": yc,
                    "n": 1,
                    "items": [{"x1": x1, "text": text, "bbox": [x1, y1, x2, y2], "region": region}],
                }
            )
    rows.sort(key=lambda row: row["yc"])
    for row in rows:
        row["items"].sort(key=lambda cell: cell["x1"])
        row["text"] = _strip_ocr_markup(" ".join(cell["text"] for cell in row["items"]))
    return rows


def load_roi_text_regions(item: Any) -> list[dict[str, Any]]:
    if not item.roi_text_path or not item.roi_text_path.exists():
        return []
    try:
        payload = _read_json(item.roi_text_path)
    except Exception:
        return []
    regions = payload.get("regions")
    return regions if isinstance(regions, list) else []
