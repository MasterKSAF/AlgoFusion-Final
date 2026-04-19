from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    clean_text,
    filter_table_rows,
    get_regions,
    group_rows,
    load_json,
    normalize_percent,
    row_texts,
    to_float,
    to_int,
)
from src.modules.runtime_invoice_helpers import (
    clean_invoice_footer_text,
    enrich_invoice_header,
    extract_invoice_note,
    extract_invoice_numeric_totals,
    extract_invoice_signatory,
    extract_invoice_total_in_words,
    is_valid_item_row,
    merge_multiline,
    normalize_unit,
    parse_invoice_header,
    parse_line_number,
)

def parse_invoice(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)

    header_box = next((r for r in regions if r.get("id") == "header_box"), None)
    footer_box = next((r for r in regions if r.get("id") == "footer_box"), None)
    table_cells = [r for r in regions if r.get("kind") == "table_cell"]

    raw_ocr_items = []
    for candidate in (
        roi_path.with_name(roi_path.name.replace("_roi_text.json", "__ocr_raw.json")),
        roi_path.with_name(roi_path.name.replace("_roi_text.json", "_ocr_raw.json")),
    ):
        if candidate.exists():
            raw_data = load_json(candidate)
            raw_ocr_items = raw_data.get("ocr_items", []) if isinstance(raw_data, dict) else []
            break

    header_text = clean_text(header_box.get("text")) if header_box else None
    raw_footer_text = clean_text(footer_box.get("text")) if footer_box else None
    footer_text = clean_invoice_footer_text(raw_footer_text)

    header_lines = header_box.get("header_lines") if header_box else None
    head = enrich_invoice_header(parse_invoice_header(header_text, header_lines, raw_ocr_items=raw_ocr_items), header_text)

    all_rows = group_rows(table_cells, tol=14)
    rows = filter_table_rows(all_rows)

    items = []
    line_no = 1
    totals = extract_invoice_numeric_totals(all_rows)

    for row in rows:
        texts = row_texts(row)

        if not is_valid_item_row(texts):
            continue

        texts = texts + [""] * (13 - len(texts))

        items.append({
            "line_number": parse_line_number(texts[0], line_no),
            "article": clean_text(texts[1]),
            "description": merge_multiline(texts[2]),
            "barcode": clean_text(texts[3]),
            "quantity": to_int(texts[4]),
            "unit": normalize_unit(texts[5]),
            "unit_price_incl_vat": to_float(texts[6]),
            "amount_no_disc_incl_vat": to_float(texts[7]),
            "disc_amount": to_float(texts[8]),
            "amount_with_disc_excl_vat": to_float(texts[9]),
            "vat_rate": normalize_percent(texts[10]),
            "vat_amount": to_float(texts[11]),
            "total_with_disc_incl_vat": to_float(texts[12]),
        })

        line_no += 1

    signatory = extract_invoice_signatory(footer_text)
    note = extract_invoice_note(footer_text)
    totals["total_in_words"] = extract_invoice_total_in_words(footer_text)

    if note:
        m2 = re.search(r'в течение\s*(\d+\s*дн\w*)', note, flags=re.I)
        if m2:
            head["payment_deadline"] = clean_text(m2.group(1))

    file_key = roi_path.name.replace("_roi_text.json", ".pdf")

    return {
        "invoice": {
            file_key: {
                "invoice_number": head["invoice_number"],
                "invoice_date": head["invoice_date"],
                "payment_deadline": head["payment_deadline"],
                "supplier": head["supplier"],
                "customer": head["customer"],
                "basis": head["basis"],
                "items": items,
                "totals": totals,
                "signatory": signatory,
                "note": note,
            }
        }
    }
