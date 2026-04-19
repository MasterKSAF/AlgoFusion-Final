from __future__ import annotations

import copy
import re
from typing import Any

from src.modules.runtime_common import region_bbox_xyxy as _region_bbox_xyxy
from src.modules.runtime_text_quality import _clean_inline_text


def group_regions_by_rows(regions: list[dict[str, Any]], kind: str = "table_cell", tol: int = 14) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    selected = [region for region in regions if region.get("kind") == kind]
    for region in sorted(selected, key=lambda row: (_region_bbox_xyxy(row)[1], _region_bbox_xyxy(row)[0])):
        y1 = _region_bbox_xyxy(region)[1]
        placed = False
        for row in rows:
            avg_y = sum(_region_bbox_xyxy(cell)[1] for cell in row) / max(1, len(row))
            if abs(y1 - avg_y) <= tol:
                row.append(region)
                placed = True
                break
        if not placed:
            rows.append([region])
    for row in rows:
        row.sort(key=lambda cell: _region_bbox_xyxy(cell)[0])
    return rows


def row_texts(regions: list[dict[str, Any]]) -> list[str]:
    return [_clean_inline_text(region.get("text")) or "" for region in regions]


def row_join_text(regions: list[dict[str, Any]]) -> str:
    return " | ".join(text for text in row_texts(regions) if text)


def make_row_region(row: list[dict[str, Any]], kind: str, prefix: str, idx: int) -> dict[str, Any] | None:
    text = row_join_text(row)
    if not text:
        return None
    boxes = [_region_bbox_xyxy(region) for region in row]
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[2] for box in boxes)
    y2 = max(box[3] for box in boxes)
    return {
        "id": f"{prefix}_{idx:03d}",
        "kind": kind,
        "bbox": [x1, y1, x2, y2],
        "text": text,
    }


def text_from_ocr_items_in_bbox(
    ocr_items: list[dict[str, Any]] | None,
    bbox: tuple[int, int, int, int],
    y_tol: int = 12,
) -> str | None:
    if not ocr_items:
        return None

    bx1, by1, bx2, by2 = bbox
    selected = []
    for item in ocr_items:
        ibox = item.get("bbox") or []
        if not isinstance(ibox, (list, tuple)) or len(ibox) != 4:
            continue
        ix1, iy1, ix2, iy2 = [int(v) for v in ibox]
        if max(0, min(ix2, bx2) - max(ix1, bx1)) <= 0:
            continue
        if max(0, min(iy2, by2) - max(iy1, by1)) <= 0:
            continue
        text = _clean_inline_text(item.get("text"))
        if not text:
            continue
        selected.append({"text": text, "bbox": (ix1, iy1, ix2, iy2)})

    if not selected:
        return None

    lines: list[list[dict[str, Any]]] = []
    for item in sorted(selected, key=lambda row: (row["bbox"][1], row["bbox"][0])):
        y1 = item["bbox"][1]
        placed = False
        for line in lines:
            avg_y = sum(entry["bbox"][1] for entry in line) / max(1, len(line))
            if abs(y1 - avg_y) <= y_tol:
                line.append(item)
                placed = True
                break
        if not placed:
            lines.append([item])

    parts = []
    for line in lines:
        line.sort(key=lambda row: row["bbox"][0])
        parts.append(" ".join(entry["text"] for entry in line))
    return _clean_inline_text(" ".join(parts))


def merge_account_prot_item_row(row: list[dict[str, Any]]) -> list[dict[str, Any]]:
    texts = row_texts(row)
    if len(row) < 11:
        return row
    unit_candidate = (texts[2] or "").lower().replace(".", "").strip()
    quantity_candidate = texts[3] or ""
    if unit_candidate not in {"шт", "шп"}:
        return row
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", quantity_candidate):
        return row

    merged = copy.deepcopy(row[0])
    bx0 = _region_bbox_xyxy(row[0])
    bx1 = _region_bbox_xyxy(row[1])
    merged["bbox"] = [
        min(bx0[0], bx1[0]),
        min(bx0[1], bx1[1]),
        max(bx0[2], bx1[2]),
        max(bx0[3], bx1[3]),
    ]
    merged["text"] = _clean_inline_text(f"{row[0].get('text', '')} {row[1].get('text', '')}") or ""
    return [merged, *[copy.deepcopy(region) for region in row[2:]]]


def normalize_account_prot_total_row(row: list[dict[str, Any]]) -> list[dict[str, Any]]:
    texts = row_texts(row)
    if not texts:
        return row
    first = (texts[0] or "").strip().lower()
    if not first.startswith("итого"):
        return row
    meaningful_tail = [region for region in row[1:] if _clean_inline_text(region.get("text"))]
    if len(meaningful_tail) < 4:
        return row
    tail = [copy.deepcopy(region) for region in meaningful_tail[-4:]]
    blanks_needed = max(0, 10 - 1 - len(tail))
    normalized = [copy.deepcopy(row[0])]
    for idx in range(blanks_needed):
        blank = copy.deepcopy(row[min(1 + idx, len(row) - 1)])
        blank["text"] = ""
        normalized.append(blank)
    normalized.extend(tail)
    return normalized[:10]


def rewrite_account_prot_row_text_from_ocr(
    row: list[dict[str, Any]],
    ocr_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not row or not ocr_items:
        return row
    bbox = _region_bbox_xyxy(row[0])
    ocr_text = text_from_ocr_items_in_bbox(ocr_items, bbox)
    if not ocr_text:
        return row
    updated = [copy.deepcopy(region) for region in row]
    updated[0]["text"] = ocr_text
    return updated
