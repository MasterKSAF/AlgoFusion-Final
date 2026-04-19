from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import MONTHS_RU, clean_text, load_json


def count_waybill_ocr_hits(full_text: str) -> int:
    cleaned = (full_text or "").strip()
    patterns = [
        r"\bТОВАРН\w*\s+НАКЛАДН\w*",
        r"\bТОВАРНО[-\s]*ТРАНСПОРТН\w*\s+НАКЛАДН\w*",
        r"\bСерия\b",
        r"Грузоотправител\w*",
        r"Грузополучател\w*",
        r"Основание\s+отпуска",
    ]
    return sum(1 for pattern in patterns if re.search(pattern, cleaned, flags=re.I))


def extract_waybill_number_from_crop_text(full_text: str, ocr_items: list[dict[str, object]]) -> str | None:
    token_items: list[dict[str, object]] = []
    crop_h = 0
    crop_w = 0
    for item in ocr_items or []:
        bbox = item.get("bbox") if isinstance(item, dict) else None
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        crop_h = max(crop_h, y2)
        crop_w = max(crop_w, x2)
        token_items.append(
            {
                "text": str(item.get("text") or "").strip() if isinstance(item, dict) else "",
                "bbox": [x1, y1, x2, y2],
                "x_mid": (x1 + x2) / 2.0,
                "y_mid": (y1 + y2) / 2.0,
            }
        )

    candidates: list[tuple[float, str]] = []
    for item in token_items:
        text = str(item["text"])
        if not text:
            continue
        for match in re.finditer(r"(?<!\d)(\d{5,8})(?!\d)", text):
            value = match.group(1)
            score = 0.0
            if len(value) == 7:
                score += 70.0
            elif len(value) == 6:
                score += 30.0
            elif len(value) == 8:
                score += 5.0
            elif len(value) == 5:
                score -= 30.0

            if crop_h > 0:
                y_ratio = float(item["y_mid"]) / crop_h
                if 0.30 <= y_ratio <= 0.70:
                    score += 120.0
                elif 0.18 <= y_ratio <= 0.80:
                    score += 60.0
                else:
                    score -= 120.0
                score += y_ratio * 30.0

            if crop_w > 0:
                x_ratio = float(item["x_mid"]) / crop_w
                if 0.15 <= x_ratio <= 0.80:
                    score += 20.0
                else:
                    score -= 20.0

            bbox = item["bbox"]
            y1, y2 = int(bbox[1]), int(bbox[3])
            nearby_short_marker = False
            for other in token_items:
                if other is item:
                    continue
                other_text = str(other["text"])
                if not other_text or len(other_text) > 4:
                    continue
                other_bbox = other["bbox"]
                oy1, oy2 = int(other_bbox[1]), int(other_bbox[3])
                overlap = min(y2, oy2) - max(y1, oy1)
                if overlap <= 0:
                    continue
                if float(other["x_mid"]) < float(item["x_mid"]):
                    nearby_short_marker = True
                    break
            if nearby_short_marker:
                score += 25.0

            candidates.append((score, value))

    if candidates:
        candidates.sort(key=lambda pair: (pair[0], len(pair[1]), pair[1]), reverse=True)
        return candidates[0][1]

    values = re.findall(r"(?<!\d)(\d{5,8})(?!\d)", full_text or "")
    if not values:
        return None
    preferred = [value for value in values if len(value) == 7]
    if preferred:
        return preferred[-1]
    return values[-1]


def _load_waybill_header_ocr(roi_path: Path):
    candidate = roi_path.with_name(roi_path.name.replace('_roi_text.json', '__waybill_header_ocr.json'))
    if candidate.exists():
        data = load_json(candidate)
        return data if isinstance(data, dict) else None
    return None

def _waybill_extract_document_number_from_header_ocr(header_ocr):
    if not isinstance(header_ocr, dict):
        return None

    full_text = clean_text(header_ocr.get('full_text'))
    if full_text:
        m = re.search(r'Серия\s+[A-ZА-Я]{1,4}\s+([0-9]{4,10})', full_text, flags=re.I)
        if m:
            return clean_text(m.group(1))

    items = header_ocr.get('ocr_items') or []
    crop_bbox = header_ocr.get('crop_bbox') or [0, 0, 0, 0]
    crop_center_x = (crop_bbox[0] + crop_bbox[2]) / 2 if len(crop_bbox) == 4 else None
    candidates = []

    for item in items:
        text = clean_text(item.get('text'))
        bbox = item.get('bbox') or [0, 0, 0, 0]
        if not text or len(bbox) != 4:
            continue
        m = re.fullmatch(r'([0-9]{5,8})', text)
        if not m:
            continue
        center_x = (bbox[0] + bbox[2]) / 2
        center_dist = abs(center_x - crop_center_x) if crop_center_x is not None else 0
        candidates.append((bbox[1], center_dist, -len(m.group(1)), m.group(1)))

    if not candidates:
        return None

    candidates.sort()
    return clean_text(candidates[0][3])

def _waybill_extract_date_from_header_ocr(header_ocr):
    if not isinstance(header_ocr, dict):
        return None

    full_text = clean_text(header_ocr.get('full_text'))
    if not full_text:
        return None

    m = re.search(r'([0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2}\s*г?\.?)', full_text, flags=re.I)
    if m:
        return clean_text(m.group(1))

    return None
