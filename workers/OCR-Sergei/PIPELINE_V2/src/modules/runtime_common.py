from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from src.modules.runtime_io import ensure_dir


def bbox_xyxy(roi: dict[str, Any]) -> tuple[int, int, int, int] | None:
    bbox = roi.get("bbox") or {}
    if isinstance(bbox, dict):
        try:
            return int(bbox["x1"]), int(bbox["y1"]), int(bbox["x2"]), int(bbox["y2"])
        except Exception:
            return None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        return int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
    return None


def zone_text(ocr_items: list[dict[str, Any]], y0: int, y1: int) -> str:
    parts = []
    for item in ocr_items:
        bbox = item.get("bbox") or [0, 0, 0, 0]
        if len(bbox) != 4:
            continue
        iy0, iy1 = int(bbox[1]), int(bbox[3])
        mid = (iy0 + iy1) / 2
        if y0 <= mid < y1:
            text = str(item.get("text", "")).strip()
            if text:
                parts.append(text)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def ocr_text_from_items(ocr_items: list[dict[str, Any]] | None) -> str:
    parts: list[str] = []
    for item in sorted(ocr_items or [], key=lambda row: ((row.get("bbox") or [0, 0, 0, 0])[1], (row.get("bbox") or [0, 0, 0, 0])[0])):
        text = str(item.get("text", "")).strip()
        if text:
            parts.append(text)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def page_no_from_page_id(page_id: str) -> int:
    match = re.search(r"__p(\d+)$", str(page_id))
    return int(match.group(1)) if match else 1


def doc_stem_from_page_id(page_id: str) -> str:
    page_id = str(page_id)
    return page_id.rsplit("__p", 1)[0] if "__p" in page_id else page_id


def keyword_score(text: str, patterns: list[str]) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.I))


def has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)


def bbox_value(roi: dict[str, Any], key: str) -> int:
    bbox = roi.get("bbox") or {}
    if isinstance(bbox, dict):
        return int(bbox.get(key, 0))
    mapping = {"x1": 0, "y1": 1, "x2": 2, "y2": 3}
    idx = mapping[key]
    return int(bbox[idx]) if len(bbox) > idx else 0


def set_bbox_value(roi: dict[str, Any], key: str, value: int) -> None:
    bbox = roi.get("bbox") or {}
    if isinstance(bbox, dict):
        bbox[key] = int(value)
        if all(k in bbox for k in ("x1", "y1", "x2", "y2")):
            bbox["w"] = max(0, int(bbox["x2"]) - int(bbox["x1"]))
            bbox["h"] = max(0, int(bbox["y2"]) - int(bbox["y1"]))
        roi["bbox"] = bbox
        return
    mapping = {"x1": 0, "y1": 1, "x2": 2, "y2": 3}
    idx = mapping[key]
    coords = list(bbox)
    while len(coords) < 4:
        coords.append(0)
    coords[idx] = int(value)
    roi["bbox"] = coords


def region_bbox_xyxy(region: dict[str, Any]) -> tuple[int, int, int, int]:
    bbox = bbox_xyxy(region)
    return bbox or (0, 0, 0, 0)


def strip_ocr_markup(text: Any) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned.replace("\xa0", " ")).strip()
    return cleaned
