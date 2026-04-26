from __future__ import annotations

import copy
import re
from typing import Any

from src.modules.runtime_numbers import (
    WAYBILL_LINKED_NUMERIC_FIELDS,
    coerce_number,
    extract_first_numeric_token,
    maybe_integral_quantity,
    numeric_close,
)
from src.modules.runtime_numeric_reconciliation import finalize_waybill_numeric_row
from src.modules.runtime_text_quality import _clean_inline_text, _is_review_field_marker
from src.modules.runtime_waybill_text import extract_waybill_unit_token


def _normalize_waybill_rate_candidate(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    match = re.fullmatch(r"(0|10|20)(?:[.,]\d{1,2})?\s*%?", cleaned)
    if not match:
        return None
    return f"{int(match.group(1))}%"


def waybill_parse_percent_text(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    match = re.search(r"(\d{1,2})(?:[.,]\d{1,2})?\s*%", cleaned)
    if match:
        return _normalize_waybill_rate_candidate(match.group(0))
    return _normalize_waybill_rate_candidate(cleaned)


def normalize_waybill_raw_unit_token(text: Any) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    compact = cleaned.lower()
    compact = compact.replace("\u03c4", "\u0442").replace("\u03a4", "\u0442")
    compact = compact.replace("t", "\u0442")
    compact = re.sub(r"[\s._|/\\-]+", "", compact)
    if compact == "\u0448\u0442":
        return "\u0448\u0442"
    normalized = extract_waybill_unit_token(cleaned)
    if normalized:
        return normalized

    collapsed = cleaned.lower().replace("ё", "е")
    collapsed = re.sub(r"[\s._|/\\-]+", "", collapsed)
    if not collapsed or re.search(r"\d", collapsed):
        return None
    if re.fullmatch(r"[wшщтtτπ]{1,4}", collapsed):
        return "шт"
    if collapsed in {"wr", "wt", "iut", "iuit", "şt"}:
        return "шт"
    if re.search(r"[\u0370-\u03ff\u0600-\u06ff\u0100-\u017f]", collapsed) and len(collapsed) <= 5:
        return "шт"
    return None


def dominant_waybill_repair_unit(items: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for row in items:
        if not isinstance(row, dict):
            continue
        unit = normalize_waybill_raw_unit_token(row.get("unit"))
        if not unit:
            continue
        counts[unit] = counts.get(unit, 0) + 1
    if not counts:
        return None
    unit, count = max(counts.items(), key=lambda pair: pair[1])
    return unit if count >= 2 else None


def waybill_numeric_token_values(text: str) -> list[float]:
    prepared = _clean_inline_text(text) or ""
    if not prepared:
        return []
    prepared = re.sub(r"(?<=\d)[:;](?=\d{2}\b)", ",", prepared)
    prepared = re.sub(r"(?<=\d)[OОoо](?=\d)", "0", prepared)
    values: list[float] = []
    for match in re.finditer(r"(?<!\d)(\d{1,6}(?:[.,]\d{1,2})?)(?!\d)", prepared):
        raw = match.group(1)
        if len(re.sub(r"\D", "", raw)) >= 8:
            continue
        value = extract_first_numeric_token(raw, allow_integer=True)
        if value is not None:
            values.append(float(value))
    return values


def waybill_find_tail_unit(text: str) -> str | None:
    unit, _end = waybill_find_tail_unit_with_end(text)
    return unit


def waybill_find_tail_unit_with_end(text: str) -> tuple[str | None, int | None]:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None, None
    best_unit = None
    best_end = None
    for match in re.finditer(r"[^\W\d_]{1,8}", cleaned, flags=re.UNICODE):
        candidate = normalize_waybill_raw_unit_token(match.group(0))
        if candidate:
            best_unit = candidate
            best_end = match.end()
    return best_unit, best_end


def _waybill_numeric_review_count(row: dict[str, Any]) -> int:
    return sum(1 for field in WAYBILL_LINKED_NUMERIC_FIELDS if _is_review_field_marker(row.get(field)))


def waybill_build_numeric_candidate(
    before_rate_values: list[float],
    after_rate_values: list[float],
    *,
    unit: str | None,
    vat_rate: str | None,
) -> dict[str, Any] | None:
    if not before_rate_values or not vat_rate:
        return None

    best: dict[str, Any] | None = None
    best_score = -1
    candidates: list[tuple[float | None, float | None, float | None]] = []
    amount_variants: list[tuple[float | None, float | None]] = []

    vat_amount = after_rate_values[0] if after_rate_values else None
    total = after_rate_values[1] if len(after_rate_values) >= 2 else None
    if total is None and vat_amount is not None and len(before_rate_values) >= 1:
        cost_guess = before_rate_values[-1]
        total = round(cost_guess + vat_amount, 2)
    amount_variants.append((vat_amount, total))

    # Some rows keep only the post-rate total instead of an explicit VAT amount.
    if len(after_rate_values) == 1:
        amount_variants.append((None, after_rate_values[0]))

    if len(before_rate_values) >= 3:
        for qty_idx, qty_value in enumerate(before_rate_values[:-2]):
            qty = maybe_integral_quantity(qty_value)
            if qty is None or qty <= 0 or qty > 500:
                continue
            for price_idx in range(qty_idx + 1, len(before_rate_values) - 1):
                price = before_rate_values[price_idx]
                cost = before_rate_values[-1]
                if price <= 0 or cost < 0:
                    continue
                candidates.append((qty, price, cost))

    explicit_first_qty = maybe_integral_quantity(before_rate_values[0]) if before_rate_values else None
    if len(before_rate_values) >= 3 and explicit_first_qty is not None and 0 < explicit_first_qty <= 500:
        candidates.append((explicit_first_qty, None, before_rate_values[-1]))

    explicit_qty_seen = any(
        (maybe_integral_quantity(value) is not None and 0 < float(maybe_integral_quantity(value) or 0) <= 500)
        for value in before_rate_values[:-2]
    )
    if len(before_rate_values) >= 2 and (len(before_rate_values) <= 2 or not explicit_qty_seen):
        price = before_rate_values[-2]
        cost = before_rate_values[-1]
        qty = maybe_integral_quantity(cost / price) if price else None
        candidates.append((qty, price, cost))

    if len(before_rate_values) == 1 and total is not None and vat_amount is not None:
        price = before_rate_values[0]
        cost = round(total - vat_amount, 2)
        qty = maybe_integral_quantity(cost / price) if price else None
        candidates.append((qty, price, cost))

    for qty, price, cost in candidates:
        for candidate_vat_amount, candidate_total in amount_variants:
            row = {
                "unit": unit,
                "quantity": coerce_number(qty),
                "price": coerce_number(price),
                "cost": coerce_number(cost),
                "vat_rate": vat_rate,
                "vat_amount": coerce_number(candidate_vat_amount),
                "cost_with_vat": coerce_number(candidate_total),
            }
            finalized = finalize_waybill_numeric_row(copy.deepcopy(row))
            review_count = _waybill_numeric_review_count(finalized)
            if review_count != 0:
                continue
            relation_score = 0
            if qty is not None and price is not None and cost is not None and numeric_close(cost, qty * price):
                relation_score += 3
            if qty is not None and price is None and cost is not None:
                relation_score += 2
            if (
                cost is not None
                and candidate_vat_amount is not None
                and candidate_total is not None
                and numeric_close(candidate_total, cost + candidate_vat_amount)
            ):
                relation_score += 2
            if candidate_vat_amount is None and candidate_total is not None:
                relation_score += 1
            if (
                len(after_rate_values) == 1
                and candidate_vat_amount is None
                and candidate_total is not None
                and cost is not None
                and numeric_close(candidate_total, cost, abs_tol=0.03, rel_tol=0.2)
            ):
                relation_score += 4
            score = (6 - review_count) * 10 + relation_score
            if score > best_score:
                best = finalized
                best_score = score

    return best


def waybill_parse_numeric_candidate_from_text(line: str, default_unit: str | None = None) -> dict[str, Any] | None:
    cleaned = _clean_inline_text(line) or ""
    if not cleaned:
        return None
    rate_match = re.search(r"(\d{1,2})(?:[.,]\d{1,2})?\s*%", cleaned)
    if rate_match:
        vat_rate = waybill_parse_percent_text(rate_match.group(0))
        if not vat_rate:
            return None

        before = cleaned[: rate_match.start()]
        after = cleaned[rate_match.end() :]
        after = re.split(r"\b(?:\u0446\u0435\u043d\u0430\s+\u043e\u0442\u043f\u0443\u0441\u043a\w*|\u0441\u043a\u0438\u0434\u043a\w*)\b", after, maxsplit=1, flags=re.I)[0]
        unit, unit_end = waybill_find_tail_unit_with_end(before)
        unit = unit or default_unit
        before_numeric_source = before[unit_end:] if unit_end is not None else before
        before_values = waybill_numeric_token_values(before_numeric_source)
        after_values = waybill_numeric_token_values(after)
        candidate = waybill_build_numeric_candidate(before_values, after_values, unit=unit, vat_rate=vat_rate)
        if candidate and candidate.get("unit") is None and default_unit:
            candidate["unit"] = default_unit
        return candidate

    unit, unit_end = waybill_find_tail_unit_with_end(cleaned)
    unit = unit or default_unit
    numeric_source = cleaned[unit_end:] if unit_end is not None else cleaned
    numeric_values = waybill_numeric_token_values(numeric_source)
    for idx, value in enumerate(numeric_values):
        rounded = int(round(value))
        if abs(value - rounded) > 0.01 or rounded not in {0, 10, 20}:
            continue
        before_values = numeric_values[:idx]
        after_values = numeric_values[idx + 1 :]
        candidate = waybill_build_numeric_candidate(
            before_values,
            after_values,
            unit=unit,
            vat_rate=f"{rounded}%",
        )
        if candidate:
            if candidate.get("unit") is None and default_unit:
                candidate["unit"] = default_unit
            return candidate
    return None


def waybill_extract_total_before_note(line: str) -> float | None:
    cleaned = _clean_inline_text(line) or ""
    match = re.search(r"(\d+[.,]\d{1,2})\s*(?:\||\s+)?\s*цена\s+отпускн", cleaned, flags=re.I)
    if not match:
        return None
    if not re.search(r"\d{1,2}\s*%", cleaned[: match.start()]):
        return None
    return extract_first_numeric_token(match.group(1), allow_integer=False)


def waybill_parse_inline_numeric_tail(line: str) -> dict[str, Any] | None:
    cleaned = _clean_inline_text(line) or ""
    if not cleaned:
        return None
    match = re.search(
        r"\b([A-Za-z\u0410-\u044f\u0401\u0451\u03c4\u03c0]{1,6})\b\s+(\d{1,3})\s+(\d+[.,;]\d{1,2})\s+(\d+[.,;]\d{1,2})\s+(\d{1,2}(?:\s*%)?)\s+(\d+[.,;]\d{1,2})(?:\s+(\d+[.,;]\d{1,2}))?",
        cleaned,
        flags=re.I,
    )
    if not match:
        return None
    normalized_unit = normalize_waybill_raw_unit_token(match.group(1))
    if not normalized_unit:
        return None
    vat_rate = _normalize_waybill_rate_candidate(match.group(5))
    if not vat_rate:
        return None
    return {
        "unit": normalized_unit,
        "quantity": int(match.group(2)),
        "price": extract_first_numeric_token(match.group(3), allow_integer=False),
        "cost": extract_first_numeric_token(match.group(4), allow_integer=False),
        "vat_rate": vat_rate,
        "vat_amount": extract_first_numeric_token(match.group(6), allow_integer=False),
        "cost_with_vat": extract_first_numeric_token(match.group(7), allow_integer=False) if match.group(7) else None,
    }
