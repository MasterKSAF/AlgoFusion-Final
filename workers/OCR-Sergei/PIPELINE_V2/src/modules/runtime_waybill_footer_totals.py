from __future__ import annotations

import re

from src.modules.runtime_text_quality import _clean_inline_text


def normalize_waybill_total_number(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    rounded = round(float(value), 2)
    return int(rounded) if float(rounded).is_integer() else rounded


def parse_waybill_footer_numeric_token(token: str) -> float | int | None:
    cleaned = re.sub(r"\s+", "", str(token or "")).replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except Exception:
        return None
    return int(value) if value.is_integer() else value


def extract_waybill_footer_totals_from_text(text: str) -> dict[str, float | int]:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return {}

    vat_anchor_pattern = r"\u0412\u0441\u0435\u0433\u043e\s+\u0441\u0443\u043c\u043c\u0430\s+\u041d\u0414\u0421"
    total_anchor_pattern = r"\u0412\u0441\u0435\u0433\u043e\s+\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c\s+\u0441\s+\u041d\u0414\u0421"
    anchor_positions = [
        match.start()
        for pattern in [vat_anchor_pattern, total_anchor_pattern]
        for match in [re.search(pattern, cleaned, flags=re.I)]
        if match
    ]
    if not anchor_positions:
        return {}

    anchor_pos = min(anchor_positions)
    window = cleaned[max(0, anchor_pos - 180) : anchor_pos]
    numeric_tokens = re.findall(r"\d{1,3}(?:\s\d{3})+[.,]\d{1,2}|\d+[.,]\d{1,2}|\d+", window)
    parsed_tokens: list[tuple[str, float | int]] = []
    for token in numeric_tokens:
        parsed = parse_waybill_footer_numeric_token(token)
        if parsed is None:
            continue
        parsed_tokens.append((token, parsed))
    if not parsed_tokens:
        return {}

    decimal_values = [float(value) for token, value in parsed_tokens if "," in token or "." in token]
    out: dict[str, float | int] = {}
    has_total_label = bool(re.search(r"\b\u0418\u0442\u043e\u0433\u043e\b", window, flags=re.I))
    qty_match = re.search(r"\b\u0418\u0442\u043e\u0433\u043e\b[^\d]{0,12}(\d{1,6})(?![.,]\d)", window, flags=re.I)
    if qty_match:
        out["quantity_total"] = int(qty_match.group(1))

    if has_total_label and len(decimal_values) >= 3:
        last_three = sorted(decimal_values[-3:])
        if abs((last_three[0] + last_three[1]) - last_three[2]) <= 0.2:
            out["vat_total"] = normalize_waybill_total_number(last_three[0])
            out["cost_total"] = normalize_waybill_total_number(last_three[1])
            out["cost_with_vat_total"] = normalize_waybill_total_number(last_three[2])
            return out

    if has_total_label and len(decimal_values) >= 2:
        pair = sorted(decimal_values[-2:])
        if pair[1] > pair[0]:
            out["vat_total"] = normalize_waybill_total_number(pair[0])
            out["cost_with_vat_total"] = normalize_waybill_total_number(pair[1])
            out["cost_total"] = normalize_waybill_total_number(pair[1] - pair[0])
            return out

    return out


def waybill_totals_incoherent(
    quantity_total: float | int | None,
    cost_total: float | int | None,
    vat_total: float | int | None,
    cost_with_vat_total: float | int | None,
) -> bool:
    try:
        quantity = float(quantity_total) if quantity_total is not None else None
    except Exception:
        quantity = None
    try:
        cost = float(cost_total) if cost_total is not None else None
    except Exception:
        cost = None
    try:
        vat = float(vat_total) if vat_total is not None else None
    except Exception:
        vat = None
    try:
        total = float(cost_with_vat_total) if cost_with_vat_total is not None else None
    except Exception:
        total = None

    if quantity is not None and quantity <= 0:
        return True
    if total is not None and vat is not None and total + 0.01 < vat:
        return True
    if total is not None and cost is not None and total + 0.01 < cost:
        return True
    if total is not None and cost is not None and vat is not None and abs((cost + vat) - total) > 0.2:
        return True
    return False
