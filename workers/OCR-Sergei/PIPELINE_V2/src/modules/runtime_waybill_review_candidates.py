from __future__ import annotations

import re
from typing import Any

from shared.resources.text_lexicon import WAYBILL_BRIDGE_CONTEXT_PATTERN, WAYBILL_NOTE_TAIL_MARKERS
from src.modules.runtime_numbers import WAYBILL_LINKED_NUMERIC_FIELDS, extract_first_numeric_token
from src.modules.runtime_text_quality import _clean_inline_text, _is_review_field_marker
from src.modules.runtime_waybill_numeric_candidates import (
    normalize_waybill_raw_unit_token,
    waybill_extract_total_before_note,
    waybill_parse_inline_numeric_tail,
    waybill_parse_numeric_candidate_from_text,
    waybill_parse_percent_text,
)
from src.modules.runtime_waybill_review_windows import extract_waybill_barcode_from_name, waybill_significant_name_tokens


def split_waybill_raw_cells(line: str) -> list[str]:
    return [cell for cell in [_clean_inline_text(part) for part in re.split(r"\s*\|\s*", line or "")] if cell]


def _waybill_numeric_review_count(row: dict[str, Any]) -> int:
    return sum(1 for field in WAYBILL_LINKED_NUMERIC_FIELDS if _is_review_field_marker(row.get(field)))


def _waybill_leading_item_code(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    match = re.match(r"^\s*([A-Za-zА-Яа-я0-9]{1,8}/[A-Za-zА-Яа-я0-9]{1,8})\b", cleaned)
    return match.group(1).lower() if match else None


def _looks_like_waybill_numeric_tail_line(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    if re.search(r"\d{1,3}\s+\d+[.,]\d{1,2}\s+\d+[.,]\d{1,2}\s+\d{1,2}\s*%\s+\d+[.,]\d{1,2}", cleaned):
        return True
    if re.search(r"\d+[.,]\d{1,2}.*\d+[.,]\d{1,2}.*\d{1,2}\s*%.*\d+[.,]\d{1,2}.*\d+[.,]\d{1,2}", cleaned):
        return True
    return bool(waybill_parse_inline_numeric_tail(cleaned))


def _looks_like_waybill_bridge_context_line(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    return bool(re.search(WAYBILL_BRIDGE_CONTEXT_PATTERN, cleaned, flags=re.I))


def waybill_review_row_candidate_from_window(lines: list[str], default_unit: str | None = None) -> dict[str, Any] | None:
    if not lines:
        return None

    robust_candidates: list[dict[str, Any]] = []
    for source in [line for line in lines if line] + [" ".join(line for line in lines if line)]:
        candidate = waybill_parse_numeric_candidate_from_text(source, default_unit=default_unit)
        if candidate:
            robust_candidates.append(candidate)
    if robust_candidates:
        robust_candidates.sort(key=lambda row: _waybill_numeric_review_count(row))
        if _waybill_numeric_review_count(robust_candidates[0]) == 0:
            return robust_candidates[0]

    quantity = None
    price = None
    cost = None
    vat_amount = None
    total = None
    unit = None
    vat_rate = None

    for line in lines:
        inline_tail = waybill_parse_inline_numeric_tail(line)
        if inline_tail:
            unit = inline_tail.get("unit") or unit
            quantity = inline_tail.get("quantity") or quantity
            price = inline_tail.get("price") if inline_tail.get("price") is not None else price
            cost = inline_tail.get("cost") if inline_tail.get("cost") is not None else cost
            vat_rate = inline_tail.get("vat_rate") or vat_rate
            vat_amount = inline_tail.get("vat_amount") if inline_tail.get("vat_amount") is not None else vat_amount
            total = inline_tail.get("cost_with_vat") if inline_tail.get("cost_with_vat") is not None else total

        candidate_total = waybill_extract_total_before_note(line)
        if candidate_total is not None:
            total = candidate_total
        cells = split_waybill_raw_cells(line)
        if not cells:
            continue
        if vat_rate is None:
            for cell in cells:
                vat_rate = waybill_parse_percent_text(cell) or vat_rate
        if unit is None:
            for cell in cells:
                unit = normalize_waybill_raw_unit_token(cell) or unit

        unit_idx = next((idx for idx, cell in enumerate(cells) if normalize_waybill_raw_unit_token(cell)), None)
        if unit_idx is None:
            continue

        if quantity is None:
            for idx in (unit_idx + 1, unit_idx - 1, unit_idx + 2):
                if 0 <= idx < len(cells):
                    raw_qty = extract_first_numeric_token(cells[idx])
                    if raw_qty is not None and abs(raw_qty - round(raw_qty)) <= 1e-6 and 0 < raw_qty <= 500:
                        quantity = int(round(raw_qty))
                        break

        seen_rate = False
        numeric_before_rate: list[float] = []
        numeric_after_rate: list[float] = []
        for cell in cells[unit_idx + 1 :]:
            lowered = cell.lower()
            if any(marker in lowered for marker in WAYBILL_NOTE_TAIL_MARKERS):
                break
            if waybill_parse_percent_text(cell):
                seen_rate = True
                continue
            if re.search(r"\d{8,14}", cell):
                continue
            value = extract_first_numeric_token(cell, allow_integer=True)
            if value is None:
                continue
            if seen_rate:
                numeric_after_rate.append(value)
            else:
                numeric_before_rate.append(value)

        if quantity is None and numeric_before_rate and abs(numeric_before_rate[0] - round(numeric_before_rate[0])) <= 1e-6:
            qty_candidate = int(round(numeric_before_rate[0]))
            if 0 < qty_candidate <= 500:
                quantity = qty_candidate
                numeric_before_rate = numeric_before_rate[1:]

        if price is None and numeric_before_rate:
            price = numeric_before_rate[0]
        if cost is None and len(numeric_before_rate) >= 2:
            cost = numeric_before_rate[1]
        if vat_amount is None and numeric_after_rate:
            vat_amount = numeric_after_rate[0]
        if total is None and len(numeric_after_rate) >= 2:
            total = numeric_after_rate[1]

    if quantity is None or unit is None:
        for line in lines:
            if not any(marker in (line or "").lower() for marker in WAYBILL_NOTE_TAIL_MARKERS):
                continue
            cells = split_waybill_raw_cells(line)
            prefix_cells = []
            for cell in cells:
                if any(marker in cell.lower() for marker in WAYBILL_NOTE_TAIL_MARKERS):
                    break
                prefix_cells.append(cell)
            numeric_prefix = [
                extract_first_numeric_token(cell, allow_integer=True)
                for cell in prefix_cells
                if not re.search(r"\d{8,14}", cell)
            ]
            numeric_prefix = [value for value in numeric_prefix if value is not None]
            if quantity is None and len(numeric_prefix) >= 1 and abs(numeric_prefix[0] - round(numeric_prefix[0])) <= 1e-6:
                qty_candidate = int(round(numeric_prefix[0]))
                if 0 < qty_candidate <= 500:
                    quantity = qty_candidate
            if price is None and len(numeric_prefix) >= 2:
                price = numeric_prefix[-1]
            if total is None and numeric_prefix:
                total = numeric_prefix[-1]

    candidate = {
        "unit": unit or default_unit,
        "quantity": quantity,
        "price": price,
        "cost": cost,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "cost_with_vat": total,
    }
    if all(value is None for value in candidate.values()):
        return None
    return candidate


def waybill_trim_window_to_row(lines: list[str], row: dict[str, Any]) -> list[str]:
    if not lines:
        return lines
    barcode = extract_waybill_barcode_from_name(row.get("name"))
    item_code = _waybill_leading_item_code(row.get("name"))
    tokens = waybill_significant_name_tokens(row.get("name"))
    best_idx = None
    best_score = 0
    for idx, line in enumerate(lines):
        if barcode and barcode in line:
            start_idx = idx
            found_numeric_anchor = False
            seen_related_context = False
            for probe_idx in range(idx - 1, max(-1, idx - 4), -1):
                if probe_idx < 0:
                    break
                prev_line = lines[probe_idx]
                prev_lowered = (prev_line or "").lower()
                prev_tokens_score = sum(1 for token in tokens if token in prev_lowered)
                prev_item_code = _waybill_leading_item_code(prev_line)
                prev_barcodes = re.findall(r"\b\d{8,14}\b", prev_line or "")
                prev_has_foreign_barcode = any(candidate != barcode for candidate in prev_barcodes)
                prev_related = (
                    (item_code and (prev_item_code == item_code or item_code in prev_lowered))
                    or prev_tokens_score >= 1
                )
                prev_numeric = _looks_like_waybill_numeric_tail_line(prev_line)
                prev_bridge = _looks_like_waybill_bridge_context_line(prev_line)
                if prev_has_foreign_barcode:
                    break
                if prev_numeric and prev_related:
                    start_idx = probe_idx
                    found_numeric_anchor = True
                    seen_related_context = True
                    continue
                if prev_numeric:
                    start_idx = probe_idx
                    found_numeric_anchor = True
                    continue
                if prev_numeric and seen_related_context:
                    start_idx = probe_idx
                    found_numeric_anchor = True
                    continue
                if not found_numeric_anchor and prev_related:
                    start_idx = probe_idx
                    seen_related_context = True
                    continue
                if prev_bridge:
                    start_idx = probe_idx
                    continue
                break
            return lines[start_idx:]
        lowered = (line or "").lower()
        score = sum(1 for token in tokens if token in lowered)
        if score > best_score:
            best_idx = idx
            best_score = score
    threshold = 1 if len(tokens) == 1 else 2
    if best_idx is not None and best_score >= threshold:
        return lines[best_idx:]
    return lines
