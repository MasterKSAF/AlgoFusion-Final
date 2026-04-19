from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_articles import (
    clean_invoice_description_value,
    extract_invoice_barcode_cell_description,
    extract_invoice_lead_fields,
)
from src.modules.runtime_invoice_cells import (
    invoice_barcode_cell_idx,
    looks_like_integer_text,
    looks_like_invoice_qty_unit_cell,
    looks_like_money_text,
    looks_like_percent_text,
    split_invoice_qty_unit,
)
from src.modules.runtime_invoice_row_numeric_tail import (
    build_invoice_compact_numeric_tail_row,
    build_invoice_numeric_tail_row,
)
from src.modules.runtime_invoice_row_standard import parse_standard_invoice_region_nonempty
from src.modules.runtime_invoice_units import looks_like_invoice_unit_cell, normalize_invoice_unit_v2
from src.modules.runtime_numbers import coerce_number, extract_first_numeric_token
from src.modules.runtime_text_quality import _clean_inline_text


def parse_invoice_region_row(texts: list[str], fallback_line_number: int) -> dict[str, Any] | None:
    cells = [_clean_inline_text(text) or "" for text in texts]
    nonempty = [text for text in cells if text]
    if len(nonempty) < 8:
        return None
    if any(re.search(r"\b(?:итого|всего|счет\s+действителен)\b", text, flags=re.I) for text in nonempty):
        return None

    standard_row = parse_standard_invoice_region_nonempty(nonempty, fallback_line_number)
    if standard_row is not None:
        return standard_row

    if (
        len(nonempty) == 11
        and looks_like_integer_text(nonempty[0])
        and bool(re.search(r"\d{8,14}", nonempty[3]))
        and looks_like_integer_text(nonempty[4])
        and normalize_invoice_unit_v2(nonempty[5]) is not None
        and looks_like_money_text(nonempty[6])
        and looks_like_money_text(nonempty[7])
        and looks_like_percent_text(nonempty[8])
        and looks_like_money_text(nonempty[9])
        and looks_like_money_text(nonempty[10])
    ):
        quantity = coerce_number(extract_first_numeric_token(nonempty[4]))
        unit = normalize_invoice_unit_v2(nonempty[5]) or "шт"
        unit_price = coerce_number(extract_first_numeric_token(nonempty[6], allow_integer=False))
        amount_excl = coerce_number(extract_first_numeric_token(nonempty[7], allow_integer=False))
        vat_amount = coerce_number(extract_first_numeric_token(nonempty[9], allow_integer=False))
        total = coerce_number(extract_first_numeric_token(nonempty[10], allow_integer=False))
        amount_incl = None
        if quantity is not None and unit_price is not None:
            amount_incl = coerce_number(round(float(quantity) * float(unit_price), 2))
        return {
            "line_number": int(float(nonempty[0])) if extract_first_numeric_token(nonempty[0]) is not None else fallback_line_number,
            "article": _clean_inline_text(nonempty[1]),
            "description": clean_invoice_description_value(nonempty[2], article=_clean_inline_text(nonempty[1])),
            "barcode": re.search(r"(\d{8,14})", nonempty[3]).group(1),
            "quantity": quantity,
            "unit": unit,
            "unit_price_incl_vat": unit_price,
            "amount_no_disc_incl_vat": amount_incl or total,
            "disc_amount": None,
            "amount_with_disc_excl_vat": amount_excl,
            "vat_rate": (_clean_inline_text(nonempty[8]) or "").replace(" ", ""),
            "vat_amount": vat_amount,
            "total_with_disc_incl_vat": total,
        }

    percent_idx = next((idx for idx in range(len(cells) - 1, -1, -1) if looks_like_percent_text(cells[idx])), None)
    barcode_idx = invoice_barcode_cell_idx(cells)
    qty_unit_idx = next((idx for idx, text in enumerate(cells) if looks_like_invoice_qty_unit_cell(text)), None)
    qty_idx = None
    unit_idx = None
    qty_search_start = (barcode_idx + 1) if barcode_idx is not None else 0
    qty_search_stop = percent_idx if percent_idx is not None else len(cells)
    for idx in range(max(0, qty_search_start), max(0, qty_search_stop - 1)):
        if looks_like_integer_text(cells[idx]) and looks_like_invoice_unit_cell(cells[idx + 1]):
            qty_idx = idx
            unit_idx = idx + 1
            break
        if idx + 2 < qty_search_stop and looks_like_integer_text(cells[idx]) and looks_like_invoice_unit_cell(cells[idx + 2]):
            qty_idx = idx
            unit_idx = idx + 2
            break
    if percent_idx is not None and barcode_idx is not None:
        if qty_unit_idx is not None:
            quantity, unit = split_invoice_qty_unit(cells[qty_unit_idx])
            numeric_start_idx = qty_unit_idx + 1
        elif qty_idx is not None and unit_idx is not None and unit_idx > qty_idx:
            quantity = coerce_number(extract_first_numeric_token(cells[qty_idx]))
            unit = normalize_invoice_unit_v2(cells[unit_idx])
            numeric_start_idx = unit_idx + 1
        else:
            quantity = None
            unit = None
            numeric_start_idx = None

        if quantity is not None and unit and numeric_start_idx is not None and percent_idx > numeric_start_idx:
            before_rate = [cells[idx] for idx in range(numeric_start_idx, percent_idx) if _clean_inline_text(cells[idx])]
            after_rate = [cells[idx] for idx in range(percent_idx + 1, len(cells)) if _clean_inline_text(cells[idx])]
            if len(before_rate) >= 2 and len(after_rate) >= 2:
                line_number, article, description = extract_invoice_lead_fields(cells[:barcode_idx], fallback_line_number)
                if not description:
                    description = extract_invoice_barcode_cell_description(cells[barcode_idx], article=article)
                barcode_match = re.search(r"(\d{8,14})", cells[barcode_idx] or "")
                barcode = barcode_match.group(1) if barcode_match else None
                return build_invoice_numeric_tail_row(
                    line_number=line_number,
                    article=article,
                    description=description,
                    barcode=barcode,
                    quantity=quantity,
                    unit=unit,
                    before_rate=before_rate,
                    vat_rate_text=cells[percent_idx],
                    after_rate=after_rate,
                )
            if len(before_rate) >= 2 and len(after_rate) == 1:
                line_number, article, description = extract_invoice_lead_fields(cells[:barcode_idx], fallback_line_number)
                if not description:
                    description = extract_invoice_barcode_cell_description(cells[barcode_idx], article=article)
                barcode_match = re.search(r"(\d{8,14})", cells[barcode_idx] or "")
                barcode = barcode_match.group(1) if barcode_match else None
                return build_invoice_compact_numeric_tail_row(
                    line_number=line_number,
                    article=article,
                    description=description,
                    barcode=barcode,
                    quantity=quantity,
                    unit=unit,
                    price_text=before_rate[0],
                    amount_excl_text=before_rate[1],
                    vat_rate_text=cells[percent_idx],
                    trailing_value_text=after_rate[0],
                )

    qty_unit_idx = next((idx for idx, text in enumerate(cells) if looks_like_invoice_qty_unit_cell(text)), None)
    percent_idx = next((idx for idx in range(len(cells) - 1, -1, -1) if looks_like_percent_text(cells[idx])), None)
    barcode_idx = invoice_barcode_cell_idx(cells)
    if qty_unit_idx is not None and percent_idx is not None and percent_idx > qty_unit_idx:
        line_number, article, description = extract_invoice_lead_fields(
            cells[:barcode_idx] if barcode_idx is not None else cells[:qty_unit_idx],
            fallback_line_number,
        )
        if not description and barcode_idx is not None:
            description = extract_invoice_barcode_cell_description(cells[barcode_idx], article=article)
        barcode = None
        if barcode_idx is not None:
            match = re.search(r"(\d{8,14})", cells[barcode_idx] or "")
            barcode = match.group(1) if match else None
        quantity, unit = split_invoice_qty_unit(cells[qty_unit_idx])
        before_rate = [cells[idx] for idx in range(qty_unit_idx + 1, percent_idx) if _clean_inline_text(cells[idx])]
        after_rate = [cells[idx] for idx in range(percent_idx + 1, len(cells)) if _clean_inline_text(cells[idx])]
        if quantity is not None and unit and len(before_rate) >= 2 and len(after_rate) >= 2:
            return build_invoice_numeric_tail_row(
                line_number=line_number,
                article=article,
                description=description,
                barcode=barcode,
                quantity=quantity,
                unit=unit,
                before_rate=before_rate,
                vat_rate_text=cells[percent_idx],
                after_rate=after_rate,
            )
        if quantity is not None and unit and len(before_rate) >= 2 and len(after_rate) == 1:
            return build_invoice_compact_numeric_tail_row(
                line_number=line_number,
                article=article,
                description=description,
                barcode=barcode,
                quantity=quantity,
                unit=unit,
                price_text=before_rate[0],
                amount_excl_text=before_rate[1],
                vat_rate_text=cells[percent_idx],
                trailing_value_text=after_rate[0],
            )

    return None
