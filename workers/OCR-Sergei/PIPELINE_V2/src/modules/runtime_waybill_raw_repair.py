from __future__ import annotations

import copy
import re
from typing import Any

from src.modules.runtime_common import strip_ocr_markup as _strip_ocr_markup
from src.modules.runtime_numbers import WAYBILL_LINKED_NUMERIC_FIELDS
from src.modules.runtime_text_quality import _clean_inline_text, _is_review_field_marker
from src.modules.runtime_types import PageWorkItem
from src.modules.runtime_waybill_numeric import finalize_waybill_numeric_row as _finalize_waybill_numeric_row
from src.modules.runtime_waybill_numeric_candidates import (
    dominant_waybill_repair_unit as _dominant_waybill_repair_unit,
    waybill_find_tail_unit_with_end as _waybill_find_tail_unit_with_end,
)
from src.modules.runtime_waybill_review_candidates import (
    _looks_like_waybill_numeric_tail_line,
    waybill_review_row_candidate_from_window as _waybill_review_row_candidate_from_window,
    waybill_trim_window_to_row as _waybill_trim_window_to_row,
)
from src.modules.runtime_waybill_review_windows import (
    extract_waybill_barcode_from_name as _extract_waybill_barcode_from_name,
    waybill_group_raw_line_texts as _waybill_group_raw_line_texts,
    waybill_iter_review_row_windows as _waybill_iter_review_row_windows,
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(_is_missing(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_missing(item) for item in value.values())
    return False

def _extract_between_markers(text: str, start_patterns: list[str], stop_patterns: list[str]) -> str | None:
    source = str(text or "")
    best_match = None
    for pattern in start_patterns:
        match = re.search(pattern, source, flags=re.I | re.S)
        if match and (best_match is None or match.start() < best_match.start()):
            best_match = match
    if best_match is None:
        return None
    tail = source[best_match.end() :]
    stop_pos = len(tail)
    for pattern in stop_patterns:
        match = re.search(pattern, tail, flags=re.I | re.S)
        if match:
            stop_pos = min(stop_pos, match.start())
    return _strip_ocr_markup(tail[:stop_pos]) or None

def _extract_first_ru_date(text: str) -> str | None:
    source = _strip_ocr_markup(text)
    month_pattern = r"(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
    match = re.search(rf"([0-3]?\d\s+{month_pattern}\s+20\d{{2}}\s*г?\.?)", source, flags=re.I)
    if match:
        return _clean_inline_text(match.group(1))
    match = re.search(r"([0-3]?\d[./][01]?\d[./]20\d{2})", source)
    return _clean_inline_text(match.group(1)) if match else None

def _strip_leading_form_label(text: str) -> str:
    cleaned = _strip_ocr_markup(text)
    cleaned = re.sub(r"^(?:\([^)]*\)\s*)+", "", cleaned)
    cleaned = re.sub(
        r"^(?:Заказчик\s+автомобильной\s+перевозки(?:\s*\([^)]*\))?|Грузоотправитель|Грузополучатель)\s*",
        "",
        cleaned,
        flags=re.I,
    )
    return _clean_inline_text(cleaned) or ""

def _text_before_anchor(text: str, anchor_pattern: str) -> str | None:
    match = re.search(anchor_pattern, text, flags=re.I)
    if not match:
        return None
    prefix = _strip_leading_form_label(text[: match.start()])
    return _clean_inline_text(prefix)

def _text_after_anchor(text: str, anchor_pattern: str, stop_patterns: list[str] | None = None) -> str | None:
    match = re.search(anchor_pattern, text, flags=re.I)
    if not match:
        return None
    tail = text[match.end() :]
    stop_pos = len(tail)
    for pattern in stop_patterns or []:
        stop_match = re.search(pattern, tail, flags=re.I)
        if stop_match:
            stop_pos = min(stop_pos, stop_match.start())
    return _clean_inline_text(_strip_leading_form_label(tail[:stop_pos]))

def _extract_waybill_words_after_anchor(text: str, anchor_pattern: str, stop_patterns: list[str] | None = None) -> str | None:
    match = re.search(anchor_pattern, text or "", flags=re.I)
    if not match:
        return None
    tail = str(text or "")[match.end() :]
    stop_pos = len(tail)
    for pattern in stop_patterns or []:
        stop_match = re.search(pattern, tail, flags=re.I)
        if stop_match:
            stop_pos = min(stop_pos, stop_match.start())
    cleaned = _clean_inline_text(tail[:stop_pos].lstrip(" :;,-"))
    if not cleaned:
        return None
    if not re.search(r"[A-Za-z\u0410-\u044f\u0401\u0451]", cleaned):
        return None
    return cleaned

def _waybill_leading_item_code(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    match = re.match(r"^\s*([A-Za-zА-Яа-я0-9]{1,8}/[A-Za-zА-Яа-я0-9]{1,8})\b", cleaned)
    return match.group(1).lower() if match else None

def _waybill_trim_window_before_next_barcode(lines: list[str], row: dict[str, Any]) -> list[str]:
    barcode = _extract_waybill_barcode_from_name(row.get("name"))
    item_code = _waybill_leading_item_code(row.get("name"))
    if not barcode or not lines:
        return lines

    out: list[str] = []
    current_seen = False
    for line in lines:
        line_text = line or ""
        line_barcodes = re.findall(r"\b\d{8,14}\b", line_text)
        if barcode in line_barcodes:
            current_seen = True
        elif current_seen and any(candidate != barcode for candidate in line_barcodes):
            break
        elif current_seen and re.match(r"^\s*\d{1,3}\s*[\.,]", line_text):
            break
        elif current_seen and item_code:
            next_item_code = _waybill_leading_item_code(line_text)
            if next_item_code and next_item_code != item_code:
                break
        out.append(line)
    return out or lines

def _waybill_numeric_review_present(row: dict[str, Any]) -> bool:
    return any(_is_review_field_marker(row.get(field)) for field in WAYBILL_LINKED_NUMERIC_FIELDS)

def _waybill_numeric_review_count(row: dict[str, Any]) -> int:
    return sum(1 for field in WAYBILL_LINKED_NUMERIC_FIELDS if _is_review_field_marker(row.get(field)))


def _to_float_soft(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _waybill_numeric_signature_matches(row: dict[str, Any], candidate: dict[str, Any]) -> bool:
    matches = 0
    for field, tolerance in [
        ("quantity", 0.01),
        ("price", 0.05),
        ("cost", 0.05),
        ("vat_amount", 0.05),
        ("cost_with_vat", 0.05),
    ]:
        row_value = _to_float_soft(row.get(field))
        candidate_value = _to_float_soft(candidate.get(field))
        if row_value is None or candidate_value is None:
            continue
        if abs(row_value - candidate_value) > tolerance:
            return False
        matches += 1

    row_vat_rate = _clean_inline_text(row.get("vat_rate"))
    candidate_vat_rate = _clean_inline_text(candidate.get("vat_rate"))
    if row_vat_rate and candidate_vat_rate:
        if row_vat_rate != candidate_vat_rate:
            return False
        matches += 1

    return matches >= 3


def _looks_like_waybill_numbered_item_line(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    return bool(re.match(r"^\s*\d{1,3}\s*[\.,]", cleaned))


def _trim_waybill_name_piece(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    cleaned = re.sub(r"^\s*\d{1,3}\s*[\.,]\s*", "", cleaned)
    cleaned = re.sub(r"\b\u0446\u0435\u043d\u0430\s+\u043e\u0442\u043f\u0443\u0441\u043a\u043d\w*.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\u0441\u043a\u0438\u0434\u043a\w*.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[\u0370-\u03FF\u0590-\u05FF\u0600-\u06FF\u0E00-\u0E7F\u20A0-\u22FF]", "", cleaned)
    cleaned = re.sub(r"[“”„]", "", cleaned)
    numeric_chunks = re.findall(r"[\d./-]{8,}", cleaned)
    for chunk in numeric_chunks:
        digits = re.sub(r"\D", "", chunk)
        if 8 <= len(digits) <= 15:
            cleaned = cleaned.replace(chunk, digits, 1)
    cleaned = re.sub(r"(?<=\d)\s*/[A-Za-z\u0410-\u044f]{1,3}\.?", "", cleaned)
    cleaned = re.sub(r"\b\u0441\u0442\u0440\u0430\u043d\u0430\s+\u043f\u0440\u043e\u0438\u0441\u0445\.\s+[A-Za-z\u0410-\u042f]{4,}\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"([A-Za-z\u0410-\u044f]{1,4})\.,", r"\1", cleaned)
    cleaned = re.sub(r",\s*(?=\d{8,15}\b)", " ", cleaned)
    cleaned = re.sub(r",\s*(?=\u0441\u0442\u0440\u0430\u043d)", " ", cleaned, flags=re.I)
    cleaned = cleaned.strip(" ,;:-./\\")
    return cleaned or None


def _extract_waybill_anchor_name_prefix(text: Any) -> str | None:
    cleaned = _trim_waybill_name_piece(text)
    if not cleaned:
        return None

    cleaned = re.sub(
        r"\b[A-Za-z\u0410-\u044f\u0401\u0451\u03c4\u03c0]{1,8}\b\s+\d{1,3}\s+\d+[.,;]\d{1,2}\s+\d+[.,;]\d{1,2}\s+\d{1,2}(?:\s*%)?\s+\d+[.,;]\d{1,2}(?:\s+\d+[.,;]\d{1,2})?.*$",
        "",
        cleaned,
        flags=re.I,
    )
    if cleaned == (_trim_waybill_name_piece(text) or ""):
        unit, unit_end = _waybill_find_tail_unit_with_end(cleaned)
        if unit and unit_end is not None and re.search(r"\s+\d{1,3}\s+\d+[.,;]\d{1,2}", cleaned[unit_end:]):
            unit_match = re.search(rf"\b{re.escape(unit)}\b", cleaned, flags=re.I)
            if unit_match:
                cleaned = cleaned[: unit_match.start()]
    return _trim_waybill_name_piece(cleaned)


def _looks_like_waybill_barcode_or_country_line(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    return bool(
        re.search(r"\b\d{8,14}\b", cleaned)
        or re.search(r"\b\u0441\u0442\u0440\u0430\u043d\w*\b", cleaned, flags=re.I)
        or re.search(r"/\s*[A-Za-z\u0410-\u042f\u0401\u0430-\u044f\u0451]{4,}\s*/?$", cleaned)
    )


def _looks_like_waybill_name_noise_line(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return True
    if _looks_like_waybill_barcode_or_country_line(cleaned):
        return True
    if re.search(r"^[A-Za-z\u0410-\u042f]{1,5}\d{4,}\b", cleaned):
        return True
    if re.search(r"\b\d{4,}\b", cleaned) and not re.search(r"\b\d{8,14}\b", cleaned) and not re.search(r"\b\d{1,2}/\d{1,2}\b", cleaned):
        return True
    return False


def _collect_waybill_lead_name_pieces(line_texts: list[str], anchor_idx: int) -> list[str]:
    if _looks_like_waybill_numbered_item_line(line_texts[anchor_idx]):
        return []
    start_idx = max(0, anchor_idx - 8)
    for idx in range(anchor_idx - 1, start_idx - 1, -1):
        line = _clean_inline_text(line_texts[idx]) or ""
        if _looks_like_waybill_numeric_tail_line(line) or (
            re.search(r"\b\d{8,14}\b", line) and re.search(r"\b\u0441\u0442\u0440\u0430\u043d\w*\b", line, flags=re.I)
        ):
            start_idx = idx + 1
            break

    pieces: list[str] = []
    for idx in range(start_idx, anchor_idx):
        piece = _trim_waybill_name_piece(line_texts[idx])
        if not piece or _looks_like_waybill_numeric_tail_line(piece) or _looks_like_waybill_name_noise_line(piece):
            if pieces:
                break
            continue
        pieces.append(piece)
    return pieces[:4]


def _build_waybill_name_from_anchor(line_texts: list[str], anchor_idx: int) -> str | None:
    parts: list[str] = _collect_waybill_lead_name_pieces(line_texts, anchor_idx)

    anchor_piece = _extract_waybill_anchor_name_prefix(line_texts[anchor_idx])
    if anchor_piece:
        parts.append(anchor_piece)

    for idx in range(anchor_idx + 1, min(len(line_texts), anchor_idx + 4)):
        piece = _trim_waybill_name_piece(line_texts[idx])
        if not piece:
            continue
        if _looks_like_waybill_numeric_tail_line(piece):
            break
        parts.append(piece)
        if _looks_like_waybill_barcode_or_country_line(piece):
            if idx + 1 < len(line_texts):
                next_piece = _trim_waybill_name_piece(line_texts[idx + 1])
                if next_piece and not re.search(r"\d", next_piece) and not _looks_like_waybill_numeric_tail_line(next_piece):
                    parts.append(next_piece)
            break

    candidate = _clean_inline_text(" ".join(part for part in parts if part)) or ""
    if not candidate or not re.search(r"[A-Za-z\u0410-\u044f\u0401\u0451]{4,}", candidate):
        return None
    return candidate


def _waybill_numbered_item_blocks(line_texts: list[str]) -> list[tuple[int, list[str]]]:
    starts = [
        idx
        for idx, line in enumerate(line_texts)
        if re.match(r"^\s*\d{1,3}\s*[\.,]", _clean_inline_text(line) or "")
    ]
    blocks: list[tuple[int, list[str]]] = []
    for pos, start_idx in enumerate(starts):
        end_idx = starts[pos + 1] if pos + 1 < len(starts) else len(line_texts)
        block = [
            line
            for line in line_texts[start_idx:end_idx]
            if _clean_inline_text(line)
            and not re.search(
                r"^\s*(?:итого|всего\s+сумма\s+ндс|всего\s+стоимость\s+с\s+ндс)\b",
                _clean_inline_text(line),
                flags=re.I,
            )
        ]
        if block:
            blocks.append((start_idx, block))
    return blocks

def repair_waybill_review_items_from_raw(item: PageWorkItem, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items or not item.ocr_items:
        return items

    line_texts = _waybill_group_raw_line_texts(item)
    if not line_texts:
        return items

    dominant_unit = _dominant_waybill_repair_unit([row for row in items if isinstance(row, dict)])
    indexed_blocks = _waybill_numbered_item_blocks(line_texts)
    out: list[dict[str, Any]] = []
    for row_idx, row in enumerate(items, start=1):
        if not isinstance(row, dict) or not _waybill_numeric_review_present(row):
            out.append(copy.deepcopy(row) if isinstance(row, dict) else row)
            continue

        best_row = copy.deepcopy(row)
        best_review_count = _waybill_numeric_review_count(best_row)
        for window in _waybill_iter_review_row_windows(line_texts, row):
            target_window = _waybill_trim_window_to_row(window, row)
            target_window = _waybill_trim_window_before_next_barcode(target_window, row)
            candidate = _waybill_review_row_candidate_from_window(target_window, default_unit=dominant_unit)
            if not candidate:
                continue

            repaired = copy.deepcopy(row)
            for field in WAYBILL_LINKED_NUMERIC_FIELDS:
                if _is_review_field_marker(repaired.get(field)) and candidate.get(field) is not None:
                    repaired[field] = candidate.get(field)
            if (_is_review_field_marker(repaired.get("unit")) or not _clean_inline_text(repaired.get("unit"))) and candidate.get("unit"):
                repaired["unit"] = candidate.get("unit")

            repaired = _finalize_waybill_numeric_row(repaired)
            review_count = _waybill_numeric_review_count(repaired)
            if review_count < best_review_count:
                best_row = repaired
                best_review_count = review_count
            if review_count == 0:
                break

        if best_review_count > 0 and row_idx <= len(indexed_blocks):
            _block_start_idx, block = indexed_blocks[row_idx - 1]
            candidate = _waybill_review_row_candidate_from_window(block, default_unit=dominant_unit)
            if candidate:
                repaired = copy.deepcopy(row)
                for field in WAYBILL_LINKED_NUMERIC_FIELDS:
                    if _is_review_field_marker(repaired.get(field)) and candidate.get(field) is not None:
                        repaired[field] = candidate.get(field)
                if (_is_review_field_marker(repaired.get("unit")) or not _clean_inline_text(repaired.get("unit"))) and candidate.get("unit"):
                    repaired["unit"] = candidate.get("unit")
                repaired = _finalize_waybill_numeric_row(repaired)
                review_count = _waybill_numeric_review_count(repaired)
                if review_count < best_review_count:
                    best_row = repaired
                    best_review_count = review_count

        out.append(best_row)
    return out


def repair_waybill_review_item_names_from_raw(item: PageWorkItem, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items or not item.ocr_items:
        return items

    line_texts = _waybill_group_raw_line_texts(item)
    if not line_texts:
        return items

    dominant_unit = _dominant_waybill_repair_unit([row for row in items if isinstance(row, dict)])
    indexed_blocks = _waybill_numbered_item_blocks(line_texts)
    out: list[dict[str, Any]] = []
    search_start = 0

    for row_idx, row in enumerate(items, start=1):
        if not isinstance(row, dict) or not _is_review_field_marker(row.get("name")):
            out.append(copy.deepcopy(row) if isinstance(row, dict) else row)
            continue

        repaired = copy.deepcopy(row)
        anchor_idx = None
        rebuilt_name = None
        for idx in range(search_start, len(line_texts)):
            candidate = _waybill_review_row_candidate_from_window([line_texts[idx]], default_unit=dominant_unit)
            if not candidate or not _waybill_numeric_signature_matches(repaired, candidate):
                continue
            name_candidate = _build_waybill_name_from_anchor(line_texts, idx)
            if not name_candidate or _is_review_field_marker(name_candidate):
                continue
            anchor_idx = idx
            rebuilt_name = name_candidate
            break

        if rebuilt_name:
            repaired["name"] = rebuilt_name
            if anchor_idx is not None:
                search_start = anchor_idx + 1
        elif row_idx <= len(indexed_blocks):
            block_start_idx, block = indexed_blocks[row_idx - 1]
            block_candidate = _waybill_review_row_candidate_from_window(block, default_unit=dominant_unit)
            if block_candidate and (_waybill_numeric_signature_matches(repaired, block_candidate) or _waybill_numeric_review_present(repaired)):
                rebuilt_name = _build_waybill_name_from_anchor(line_texts, block_start_idx)
                if rebuilt_name and not _is_review_field_marker(rebuilt_name):
                    repaired["name"] = rebuilt_name
                    search_start = block_start_idx + 1

        out.append(repaired)

    return out
