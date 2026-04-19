from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    clean_text,
    get_regions,
    group_rows,
    is_index_row,
    load_json,
    normalize_percent,
    row_texts,
    to_float,
    to_int,
)
from src.modules.runtime_waybill_helpers import (
    _load_waybill_header_ocr,
    _waybill_extract_date_from_header_ocr,
    _waybill_extract_document_number_from_header_ocr,
    _waybill_is_total_like_item_row,
    _waybill_trim_item_name,
    enrich_waybill_result,
    extract_waybill_numeric_totals,
    extract_waybill_total_words,
    extract_waybill_unp_fields,
    parse_waybill_header,
)

def parse_waybill(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)
    header_box = next((r for r in regions if r.get("id") == "header_box"), None)
    footer_box = next((r for r in regions if r.get("id") == "footer_box"), None)
    table_cells = [r for r in regions if r.get("kind") == "table_cell"]

    header_text = clean_text(header_box.get("text")) if header_box else None
    footer_text = clean_text(footer_box.get("text")) if footer_box else None
    footer_lines = footer_box.get("footer_lines") if footer_box else None

    header_lines = header_box.get("header_lines") if header_box else None
    head = parse_waybill_header(header_text, header_lines)

    header_ocr = _load_waybill_header_ocr(roi_path)
    if isinstance(header_ocr, dict) and header_ocr.get("is_waybill_candidate_by_layout"):
        if not head.get("document_type") and header_ocr.get("is_waybill_confirmed_by_ocr"):
            head["document_type"] = "\u0422\u041e\u0412\u0410\u0420\u041d\u0410\u042f \u041d\u0410\u041a\u041b\u0410\u0414\u041d\u0410\u042f"
        if not head.get("date"):
            header_crop_date = _waybill_extract_date_from_header_ocr(header_ocr)
            if header_crop_date:
                head["date"] = header_crop_date
        if not head.get("document_number"):
            header_crop_number = _waybill_extract_document_number_from_header_ocr(header_ocr)
            if header_crop_number:
                head["document_number"] = header_crop_number

    unp_fields = extract_waybill_unp_fields(regions)
    for party_key in ("sender", "receiver", "payer"):
        party_vals = unp_fields.get(party_key) or {}
        if party_key not in head or not isinstance(head[party_key], dict):
            head[party_key] = {}
        for field, value in party_vals.items():
            if value and not head[party_key].get(field):
                head[party_key][field] = value

    all_rows = group_rows(table_cells, tol=12)

    items = []
    for row in all_rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "итого" in joined:
            continue
        if any(x in joined for x in ["наименование товара", "единица измерения", "ставка ндс", "примечание"]):
            continue
        if is_index_row(texts):
            continue
        if len(texts) < 9:
            continue
        if not texts[0] or texts[0].isdigit():
            continue
        if _waybill_is_total_like_item_row(texts):
            continue



        cost_with_vat = None
        note = clean_text(texts[8])
        if texts[7]:
            m = re.search(r'([0-9]+[.,][0-9]{2})', texts[7])
            if m:
                cost_with_vat = to_float(m.group(1))

        items.append({
            "name": _waybill_trim_item_name(texts[0]),
            "unit": "шт" if texts[1].lower() in {"шт", "шт.", "шτ"} else clean_text(texts[1]),
            "quantity": to_int(texts[2]),
            "price": to_float(texts[3]),
            "cost": to_float(texts[4]),
            "vat_rate": normalize_percent(texts[5]),
            "vat_amount": to_float(texts[6]),
            "cost_with_vat": cost_with_vat,
            "note": note,
        })

    if not head.get("document_type"):
        has_party_names = bool(head["sender"].get("name") or head["receiver"].get("name"))
        has_unp = bool(
            head["sender"].get("tax_id")
            or head["receiver"].get("tax_id")
            or head["payer"].get("tax_id")
        )
        has_waybill_structure = bool(items) and (has_party_names or has_unp) and (
            bool(table_cells) or bool(footer_box) or bool(header_box)
        )
        if has_waybill_structure:
            head["document_type"] = "ТОВАРНАЯ НАКЛАДНАЯ"

    totals = extract_waybill_numeric_totals(all_rows)
    totals["vat_total_words"] = extract_waybill_total_words(footer_lines, r'Всего сумма НДС')
    totals["cost_with_vat_total_words"] = extract_waybill_total_words(footer_lines, r'Всего стоимость с НДС')

    approvals = {
        "released_by": None,
        "handed_by": None,
        "accepted_for_delivery": None,
        "received_by": None,
        "documents_transferred": None,
    }
    footer = {"warning": None}

    return enrich_waybill_result({
        "document_type": head["document_type"],
        "document_series": head["document_series"],
        "document_number": head["document_number"],
        "date": head["date"],
        "sender": head["sender"],
        "receiver": head["receiver"],
        "payer": head["payer"],
        "basis": head["basis"],
        "items": items,
        "totals": totals,
        "approvals": approvals,
        "footer": footer,

    }, footer_text, footer_lines)
