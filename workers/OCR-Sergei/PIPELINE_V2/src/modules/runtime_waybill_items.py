from __future__ import annotations

import copy
import re
from typing import Any

from src.modules.runtime_numeric_reconciliation import (
    finalize_waybill_numeric_row,
    reconcile_waybill_item_vat_rate,
)
from src.modules.runtime_numbers import positive_number, to_float_soft
from src.modules.runtime_text_quality import (
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _review_marker_or_none,
    _sanitize_final_text_or_review,
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


def _has_waybill_footer_noise(text: str | None) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    return bool(
        re.search(
            r"не\s+подлежит|к\w{1,2}\s+формы|гознака|бумажн\w+\s+фабрик|издательств|зак\.\s*\d|третьим\s+лицам|\bуп\b|\bруп\b|внимание",
            cleaned,
            flags=re.I,
        )
    )


def _trim_waybill_footer_noise(text: str | None) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None

    stop_pos = len(cleaned)
    for pattern in [
        r"не\s+подлежит",
        r"к\w{1,2}\s+формы",
        r"гознака",
        r"бумажн\w+\s+фабрик",
        r"издательств",
        r"третьим\s+лицам",
        r"зак\.\s*\d",
        r"\bуп\b",
        r"\bруп\b",
        r"внимание",
    ]:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            stop_pos = min(stop_pos, match.start())
    cleaned = cleaned[:stop_pos]

    barcode_country_match = re.search(
        r"^(.*?\b\d{8,14}\b.*?\bстрана\s+(?:ввоза|проис\w*)\s+[A-ZА-ЯЁ]{4,}\b)",
        cleaned,
        flags=re.I,
    )
    if barcode_country_match:
        cleaned = barcode_country_match.group(1)
    else:
        first_country_match = re.search(
            r"^(.*?\bстрана\s+(?:ввоза|проис\w*)\s+[A-ZА-ЯЁ]{4,}\b)",
            cleaned,
            flags=re.I,
        )
        if first_country_match:
            tail = cleaned[first_country_match.end() :]
            if cleaned.lower().count("страна") > 1 or re.search(
                r"\b(?:[IVX]{1,4}-20\d{2}|т\.\s*\d+|зак\.\s*\d+|гознака|издательств)\b",
                tail,
                flags=re.I,
            ):
                cleaned = first_country_match.group(1)

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;.-\\/")
    return cleaned or None


def _infer_waybill_quantity(item: dict[str, Any]) -> int | float | None:
    quantity = to_float_soft(item.get("quantity"))
    if quantity is not None:
        return quantity
    price = to_float_soft(item.get("price"))
    cost = to_float_soft(item.get("cost"))
    if price is None or cost is None or abs(price) < 1e-6:
        return None
    candidate = cost / price
    rounded = round(candidate)
    if rounded > 0 and abs(candidate - rounded) <= 0.03:
        return int(rounded)
    return None


def _dominant_waybill_unit(items: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        unit = _clean_inline_text(item.get("unit"))
        if not unit:
            continue
        counts[unit] = counts.get(unit, 0) + 1
    if not counts:
        return None
    unit, count = max(counts.items(), key=lambda pair: pair[1])
    if count < 3:
        return None
    return unit


def extract_waybill_unit_token(text: Any) -> str | None:
    cleaned = (_clean_inline_text(text) or "").lower()
    if not cleaned:
        return None
    compact = cleaned
    compact = compact.replace("\u03c4", "\u0442").replace("\u03a4", "\u0442")
    compact = compact.replace("t", "\u0442")
    compact = re.sub(r"[\s._|/\\-]+", "", compact)
    if compact == "\u0448\u0442":
        return "\u0448\u0442"
    normalized = cleaned.replace("ё", "е")
    for pattern, canonical in [
        (r"\bшт\b", "шт"),
        (r"\bкг\b", "кг"),
        (r"\bг\b", "г"),
        (r"\bмл\b", "мл"),
        (r"\bл\b", "л"),
        (r"\bуп(?:ак)?\b", "уп"),
        (r"\bнабор\b", "набор"),
        (r"\bкомпл(?:ект)?\b", "компл"),
        (r"\bфл\b", "фл"),
        (r"\bпар\b", "пар"),
    ]:
        if re.search(pattern, normalized, flags=re.I):
            return canonical
    return None


def waybill_unit_suspicious(text: Any) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    if extract_waybill_unit_token(cleaned):
        alpha = re.findall(r"[A-Za-zА-Яа-яЁё]", cleaned)
        return len(alpha) > 4 or bool(re.search(r"[A-Za-zЅѕ’“]", cleaned))
    if re.search(r"\d", cleaned):
        return True
    if any(char.isalpha() for char in cleaned):
        return True
    return len(re.findall(r"[A-Za-zА-Яа-яЁё]", cleaned)) > 0


def _looks_like_waybill_non_item_row(item: dict[str, Any]) -> bool:
    name = (_clean_inline_text(item.get("name")) or "").upper()
    unit = _clean_inline_text(item.get("unit")) or ""
    note = _clean_inline_text(item.get("note")) or ""
    if not name:
        return False
    if name in {"ИТОТА", "ИТОГА", "ИТО0А"}:
        return True
    if any(marker in name for marker in ("ИТОГ", "ВСЕГО")):
        return True
    if "ИЗДАТЕЛ" in name or "БЕДБЛАНК" in name:
        return True
    combined = " ".join(part for part in [name, note] if part).strip()
    review_count = sum(
        1
        for field in ("quantity", "price", "cost", "vat_rate", "vat_amount", "cost_with_vat")
        if (_clean_inline_text(item.get(field)) or "").lower() == REVIEW_FIELD_MARKER
    )
    if combined and review_count >= 4 and not re.search(r"\d", combined):
        latin_count = len(re.findall(r"[A-Z]", combined))
        cyr_count = len(re.findall(r"[\u0410-\u042f\u0401]", combined))
        if latin_count >= 8 and cyr_count == 0:
            return True
    if not note and not unit and review_count >= 4 and re.fullmatch(r"[A-Z]{3,8}", name):
        return True
    has_item_core = positive_number(item.get("quantity")) is not None or bool(extract_waybill_unit_token(unit))
    if not has_item_core and any(to_float_soft(item.get(field)) is not None for field in ("cost", "vat_amount", "cost_with_vat")):
        return any(marker in name for marker in ("РУП", "ООО", "ОАО", "ЗАО"))
    return False


def sanitize_waybill_page_items(items: list[dict[str, Any]], page_role: str) -> list[dict[str, Any]]:
    dominant_unit = _dominant_waybill_unit(items)
    tail_start = max(0, len(items) - 2) if page_role in {"first", "single"} else len(items)
    out_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(items):
        if not isinstance(row, dict):
            continue
        out = copy.deepcopy(row)
        name = _clean_inline_text(out.get("name"))
        note = _clean_inline_text(out.get("note"))
        has_footer_noise = _has_waybill_footer_noise(name) or _has_waybill_footer_noise(note)

        if has_footer_noise or idx >= tail_start:
            trimmed_name = _trim_waybill_footer_noise(name)
            if trimmed_name:
                out["name"] = trimmed_name
            trimmed_note = _trim_waybill_footer_noise(note)
            out["note"] = trimmed_note

        inferred_qty = _infer_waybill_quantity(out)
        if inferred_qty is not None:
            out["quantity"] = inferred_qty
        normalized_unit = extract_waybill_unit_token(out.get("unit"))
        if normalized_unit:
            out["unit"] = normalized_unit
        elif dominant_unit and inferred_qty is not None and (_is_missing(out.get("unit")) or waybill_unit_suspicious(out.get("unit"))):
            out["unit"] = dominant_unit
        elif waybill_unit_suspicious(out.get("unit")):
            out["unit"] = _review_marker_or_none(out.get("unit"))

        reconciled_vat_rate = reconcile_waybill_item_vat_rate(out)
        if reconciled_vat_rate:
            current_vat_rate = _clean_inline_text(out.get("vat_rate"))
            if current_vat_rate != reconciled_vat_rate:
                out["vat_rate"] = reconciled_vat_rate

        if note:
            out["note"] = re.sub(r"^[\W_]*\d+\s+(?=цена\b)", "", note, flags=re.I)
            out["note"] = _sanitize_final_text_or_review(out.get("note"), item_text=True)

        clean_name = _clean_inline_text(out.get("name"))
        if clean_name:
            clean_name = re.sub(r"^\s*(\d+)\.\.+", r"\1.", clean_name)
            clean_name = re.sub(r"([A-Za-zА-Яа-яЁё0-9])(?:\s*[•▪●○◆■]+\s*)+$", r"\1", clean_name)
            out["name"] = _sanitize_final_text_or_review(clean_name, item_text=True)

        if _is_missing(out.get("name")):
            continue
        if _looks_like_waybill_non_item_row(out):
            continue
        out = finalize_waybill_numeric_row(out)
        out_rows.append(out)

    for line_number, row in enumerate(out_rows, start=1):
        row["line_number"] = line_number

    return out_rows
