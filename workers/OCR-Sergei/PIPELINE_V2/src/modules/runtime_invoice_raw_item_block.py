from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_raw_detection import normalize_invoice_unit
from src.modules.runtime_invoice_row_numeric_tail import build_invoice_compact_numeric_tail_row
from src.modules.runtime_numbers import coerce_number, extract_first_numeric_token
from src.modules.runtime_text_quality import _clean_inline_text


def parse_invoice_raw_item_block(block_lines: list[str], line_number: int) -> dict[str, Any] | None:
    merged = _clean_inline_text(" ".join(block_lines))
    if not merged:
        return None

    line_texts = [_clean_inline_text(line) for line in block_lines if _clean_inline_text(line)]
    if not line_texts:
        return None
    data_line_idx = max(range(len(line_texts)), key=lambda idx: line_texts[idx].count("|"))
    data_line = line_texts[data_line_idx]
    prefix_lines = line_texts[:data_line_idx]
    suffix_lines = line_texts[data_line_idx + 1 :]

    cells = [_clean_inline_text(part) for part in re.split(r"\s*\|\s*", data_line) if _clean_inline_text(part)]
    if len(cells) < 7:
        return None

    while cells and extract_first_numeric_token(cells[-1]) is None and normalize_invoice_unit(cells[-1]) is None:
        cells.pop()
    if len(cells) < 7:
        return None

    numeric_tail: list[str] = []
    idx = len(cells) - 1
    while idx >= 0 and len(numeric_tail) < 6:
        candidate = cells[idx]
        if extract_first_numeric_token(candidate) is not None or re.search(r"\b\d{1,2}(?:[.,]\d{1,2})?\s*%?\b", candidate):
            numeric_tail.append(candidate)
            idx -= 1
            continue
        break
    numeric_tail.reverse()
    if len(numeric_tail) < 5:
        return None

    # Compact invoice rows can end with:
    # barcode | "<qty> <unit>" | price | amount_excl | vat_rate | total_or_vat
    # In that layout the right-to-left numeric scan may accidentally swallow the
    # barcode as the 6th "numeric" cell. Drop it from the tail and keep it in
    # the descriptive section so downstream parsing stays aligned for the whole
    # invoice type rather than for one document instance.
    if len(numeric_tail) == 6 and re.fullmatch(r"\d{8,14}", numeric_tail[0] or ""):
        compact_qty_unit_match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s+(.+?)\s*$", numeric_tail[1] or "")
        if compact_qty_unit_match and normalize_invoice_unit(compact_qty_unit_match.group(2)):
            numeric_tail = numeric_tail[1:]
            idx += 1

    unit_text = cells[idx] if idx >= 0 else ""
    description_cells = cells[:idx] if idx >= 0 else cells[:-len(numeric_tail)]
    if description_cells and re.fullmatch(r"\d+", description_cells[0]):
        description_cells = description_cells[1:]
    description_parts = [part for part in prefix_lines + description_cells + suffix_lines if _clean_inline_text(part)]
    description = _clean_inline_text(" ".join(description_parts))
    if not description:
        return None

    article = None
    match = re.match(r"^\s*(?:\d+\s+)?([A-ZА-Я0-9][A-ZА-Я0-9./-]{2,})\b\s*(.*)$", description)
    if match:
        article = _clean_inline_text(match.group(1))
        description = _clean_inline_text(match.group(2)) or description

    barcode_match = re.search(r"(?<!\d)(\d{8,14})(?!\d)", merged)
    barcode = barcode_match.group(1) if barcode_match else None

    compact_qty_unit_match = None
    compact_quantity = None
    compact_unit = None
    if len(numeric_tail) == 5:
        qty_unit_cell = numeric_tail[0]
        compact_qty_unit_match = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s+(.+?)\s*$", qty_unit_cell or "")
        if compact_qty_unit_match:
            compact_quantity = extract_first_numeric_token(compact_qty_unit_match.group(1))
            compact_unit = normalize_invoice_unit(compact_qty_unit_match.group(2))
            if compact_quantity is not None and compact_unit:
                description_parts = [part for part in prefix_lines + description_cells + suffix_lines if _clean_inline_text(part)]
                description = _clean_inline_text(" ".join(description_parts))
                if not description:
                    return None
                compact_row = build_invoice_compact_numeric_tail_row(
                    line_number=line_number,
                    article=article,
                    description=description,
                    barcode=barcode,
                    quantity=coerce_number(compact_quantity),
                    unit=compact_unit,
                    price_text=numeric_tail[1],
                    amount_excl_text=numeric_tail[2],
                    vat_rate_text=numeric_tail[3],
                    trailing_value_text=numeric_tail[4],
                )
                if compact_row is not None:
                    return compact_row

    if len(numeric_tail) >= 6:
        qty_text, price_text, amount_text, vat_rate_text, vat_amount_text, total_text = numeric_tail[-6:]
    else:
        qty_text, price_text, amount_text, vat_rate_text, vat_amount_text, total_text = (
            numeric_tail[0],
            numeric_tail[1],
            numeric_tail[2] if len(numeric_tail) > 2 else "",
            numeric_tail[3] if len(numeric_tail) > 3 else "",
            numeric_tail[4] if len(numeric_tail) > 4 else "",
            numeric_tail[5] if len(numeric_tail) > 5 else "",
        )

    quantity = extract_first_numeric_token(qty_text)
    price = extract_first_numeric_token(price_text, allow_integer=False)
    amount = extract_first_numeric_token(amount_text, allow_integer=False)
    vat_amount = extract_first_numeric_token(vat_amount_text, allow_integer=False)
    total = extract_first_numeric_token(total_text, allow_integer=False)
    if quantity is not None and quantity <= 0:
        quantity = None
    if price is not None and price <= 0:
        price = None
    if amount is not None and amount <= 0:
        amount = None
    if vat_amount is not None and vat_amount <= 0:
        vat_amount = None
    if total is not None and total <= 0:
        total = None
    if amount is None and quantity is not None and price is not None:
        amount = round(quantity * price, 2)
    if price is None and quantity is not None and amount is not None and quantity > 0:
        price = round(amount / quantity, 2)
    if quantity is None and price is not None and amount is not None and price > 0:
        quantity = round(amount / price, 3)
    if total is None and amount is not None and vat_amount is not None:
        total = round(amount + vat_amount, 2)

    vat_rate_match = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)", vat_rate_text)
    vat_rate = None
    if vat_rate_match:
        vat_rate = f"{vat_rate_match.group(1).replace(',', '.')}%"
        vat_rate = vat_rate.replace(".0%", "%")
    if vat_amount is None and amount is not None and vat_rate:
        try:
            vat_rate_value = float(vat_rate.rstrip("%"))
        except Exception:
            vat_rate_value = None
        if vat_rate_value is not None:
            vat_amount = round(amount * vat_rate_value / 100.0, 2)
    if total is None and amount is not None and vat_amount is not None:
        total = round(amount + vat_amount, 2)

    unit = normalize_invoice_unit(unit_text) or "шт"
    if amount is None and total is None:
        return None

    return {
        "line_number": line_number,
        "article": article,
        "description": description,
        "barcode": barcode,
        "quantity": coerce_number(quantity),
        "unit": unit,
        "unit_price_incl_vat": coerce_number(price),
        "amount_no_disc_incl_vat": coerce_number(amount),
        "disc_amount": None,
        "amount_with_disc_excl_vat": coerce_number(amount),
        "vat_rate": vat_rate,
        "vat_amount": coerce_number(vat_amount),
        "total_with_disc_incl_vat": coerce_number(total),
    }
