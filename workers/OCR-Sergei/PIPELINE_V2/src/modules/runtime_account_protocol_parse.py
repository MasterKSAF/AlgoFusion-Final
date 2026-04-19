from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_account_protocol_common import (
    MONTHS_RU,
    _account_prot_extract_document_number_and_date,
    _account_prot_header_views,
    _account_prot_normalize_unit,
    extract_contract,
    split_supplier_customer,
)
from src.modules.runtime_account_protocol_footer import (
    _account_prot_extract_notes,
    _account_prot_extract_total_in_words,
)
from src.modules.runtime_account_protocol_party_parse import (
    _account_prot_parse_customer,
    _account_prot_parse_supplier,
)
from src.modules.runtime_document_parser_common import (
    clean_text,
    extract_all_bics,
    extract_ru_date_text,
    get_regions,
    group_rows,
    load_json,
    normalize_percent,
    row_texts,
    to_float,
    to_int,
)


def parse_account_protocol(roi_path: Path):
    data = load_json(roi_path)
    regions = get_regions(data)

    footer_box = next((region for region in regions if region.get("id") == "footer_box"), None)
    table_cells = [region for region in regions if region.get("kind") == "table_cell"]

    header_views = _account_prot_header_views(regions)
    header_text = header_views["header_text"]
    combined_header = header_views["combined_text"] or header_text
    footer_text = clean_text(footer_box.get("text")) if footer_box else None

    supplier_block, customer_block = split_supplier_customer(combined_header)

    if header_views["header_box_text"]:
        supplier_block = header_views["header_box_text"]

    if header_views["header_form_text"] and re.search(r'Покупатель', header_views["header_form_text"], flags=re.I):
        _form_supplier_block, form_customer_block = split_supplier_customer(header_views["header_form_text"])
        if form_customer_block:
            customer_block = form_customer_block

    supplier = _account_prot_parse_supplier(supplier_block)
    customer = _account_prot_parse_customer(customer_block)
    contract_basis = extract_contract(combined_header)

    items = []
    totals = {
        "subtotal_excl_vat": None,
        "vat_amount": None,
        "total_incl_vat": None,
        "total_in_words": None,
        "currency": "BYN",
    }

    rows = group_rows(table_cells)
    line_no = 1

    for row in rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "предмет счета" in joined:
            continue

        if texts and texts[0].strip().lower().startswith("итого"):
            if len(texts) >= 10:
                totals["subtotal_excl_vat"] = to_float(texts[6])
                totals["vat_amount"] = to_float(texts[8])
                totals["total_incl_vat"] = to_float(texts[9])
            continue

        if len(texts) < 10:
            continue

        match = re.match(r'^(\d{8,14})\s+(.*)$', texts[0])
        sku = match.group(1) if match else None
        desc = clean_text(match.group(2) if match else texts[0])

        items.append({
            "line_number": line_no,
            "sku": sku,
            "description": desc,
            "unit": _account_prot_normalize_unit(texts[1]),
            "quantity": to_int(texts[2]) or 1,
            "free_unit_price_excl_vat": to_float(texts[3]),
            "extra_charge": to_float(texts[4]),
            "unit_price_excl_vat": to_float(texts[5]),
            "total_excl_vat": to_float(texts[6]),
            "vat_rate": normalize_percent(texts[7]),
            "vat_amount": to_float(texts[8]),
            "total_incl_vat": to_float(texts[9]),
        })
        line_no += 1

    document_status = {"is_valid": None, "valid_until": None, "status_note": None}

    if footer_text:
        totals["total_in_words"] = _account_prot_extract_total_in_words(footer_text)
        status_match = re.search(
            r'(Счет действителен до:\s*[0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2}\s*г\.)',
            footer_text,
            flags=re.I,
        )
        if status_match:
            document_status["is_valid"] = True
            document_status["status_note"] = clean_text(status_match.group(1))
            document_status["valid_until"] = extract_ru_date_text(status_match.group(1))

    bics = extract_all_bics(combined_header or "")
    supplier_bics = extract_all_bics(supplier_block or "")
    customer_bics = extract_all_bics(customer_block or "")
    supplier_bank_name = (clean_text(supplier.get("bank_name")) or "").lower()
    customer_bank_name = (clean_text(customer.get("bank_name")) or "").lower()

    if not supplier.get("bank_code"):
        if supplier_bics:
            supplier["bank_code"] = supplier_bics[-1]
        elif len(bics) > 0:
            supplier["bank_code"] = bics[0]

    if not customer.get("bank_code"):
        if customer_bics:
            customer["bank_code"] = customer_bics[-1]
        elif len(bics) > 1:
            customer["bank_code"] = bics[-1]
        elif len(bics) == 1 and supplier_bank_name and supplier_bank_name == customer_bank_name:
            customer["bank_code"] = bics[0]

    document_number, document_date = _account_prot_extract_document_number_and_date(
        header_views["header_form_text"] or combined_header
    )
    if not document_number:
        document_number, document_date = _account_prot_extract_document_number_and_date(combined_header)
    if not document_date:
        document_date = extract_ru_date_text(combined_header)

    file_key = roi_path.name.replace("_roi_text.json", ".pdf")

    return {
        "Account-protocol": {
            file_key: {
                "document_number": document_number,
                "document_date": document_date,
                "supplier": supplier,
                "customer": customer,
                "contract_basis": contract_basis,
                "items": items,
                "totals": totals,
                "document_status": document_status,
                "notes": _account_prot_extract_notes(footer_text),
            }
        }
    }
