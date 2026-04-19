from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_account_protocol_parser import parse_account_protocol
from src.modules.runtime_document_parser_common import clean_text, get_regions, load_json
from src.modules.runtime_invoice_parser import (
    clean_invoice_footer_text,
    cut_basis,
    enrich_invoice_header,
    extract_invoice_note,
    extract_invoice_numeric_totals,
    extract_invoice_signatory,
    extract_invoice_total_in_words,
    extract_phone_pretty,
    invoice_is_header_row,
    invoice_is_index_row,
    is_valid_item_row,
    merge_multiline,
    normalize_unit,
    parse_invoice,
    parse_invoice_header,
    parse_line_number,
)
from src.modules.runtime_payment_order_parser import parse_payment_order
from src.modules.runtime_waybill_parser import (
    _waybill_basis_label_pattern,
    _waybill_title_from_text,
    enrich_waybill_result,
    extract_waybill_numeric_totals,
    extract_waybill_total_words,
    extract_waybill_unp_fields,
    parse_waybill,
    parse_waybill_header,
)


def _load_optional_json(path: Path):
    try:
        if path.exists():
            return load_json(path)
    except Exception:
        return None
    return None


def _collect_detection_texts(data):
    texts = []
    if not isinstance(data, dict):
        return texts

    for key in ("text", "full_text"):
        value = clean_text(data.get(key))
        if value:
            texts.append(value)

    regions = get_regions(data)
    for region in regions:
        if not isinstance(region, dict):
            continue
        value = clean_text(region.get("text"))
        if value:
            texts.append(value)
        for list_key in ("header_lines", "footer_lines", "ocr_items"):
            for item in region.get(list_key) or []:
                item_text = clean_text(item.get("text")) if isinstance(item, dict) else clean_text(item)
                if item_text:
                    texts.append(item_text)

    for item in data.get("ocr_items") or []:
        item_text = clean_text(item.get("text")) if isinstance(item, dict) else clean_text(item)
        if item_text:
            texts.append(item_text)

    seen = set()
    unique = []
    for text in texts:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(text)
    return unique


def _collect_detection_context(path: Path):
    payloads = []
    primary = _load_optional_json(path)
    if primary:
        payloads.append(primary)

    if path.name.endswith("_roi_text.json"):
        for candidate in (
            path.with_name(path.name.replace("_roi_text.json", "__ocr_raw.json")),
            path.with_name(path.name.replace("_roi_text.json", "_ocr_raw.json")),
            path.with_name(path.name.replace("_roi_text.json", "__waybill_header_ocr.json")),
        ):
            related = _load_optional_json(candidate)
            if related:
                payloads.append(related)

    texts = []
    for payload in payloads:
        texts.extend(_collect_detection_texts(payload))

    combined_text = clean_text(" ".join(texts)) or ""
    roi_data = primary if isinstance(primary, dict) else {}
    regions = get_regions(roi_data)
    table_cells = [r for r in regions if r.get("kind") == "table_cell"]
    form_rois = [r for r in regions if r.get("kind") == "form_roi"]
    header_box = next((r for r in regions if r.get("id") == "header_box"), None)
    footer_box = next((r for r in regions if r.get("id") == "footer_box"), None)
    unp_fields = extract_waybill_unp_fields(regions)
    unp_hits = sum(
        1
        for key in ("sender", "receiver", "payer")
        if (unp_fields.get(key) or {}).get("tax_id")
    )

    return {
        "text": combined_text,
        "regions": regions,
        "table_cells": table_cells,
        "form_rois": form_rois,
        "header_box": header_box,
        "footer_box": footer_box,
        "unp_hits": unp_hits,
    }


def _detect_doc_type_from_content(path: Path):
    context = _collect_detection_context(path)
    text = context["text"]
    if not text:
        return None

    if re.search(r'СЧ[ЕЁ]Т[-\s]*ПРОТОКОЛ', text, flags=re.I):
        return "account_prot"

    if re.search(r'ПЛАТ[ЕЁ]ЖН\w*\s+ПОРУЧЕН', text, flags=re.I):
        return "payment_order"

    if _waybill_title_from_text(text):
        return "waybill"

    if (
        re.search(r'\bСЧ[ЕЁ]Т\b', text, flags=re.I)
        and re.search(r'\bПоставщик\b', text, flags=re.I)
        and re.search(r'\bПокупател', text, flags=re.I)
        and re.search(r'\bОснован', text, flags=re.I)
    ):
        return "invoice"

    has_waybill_parties = bool(
        re.search(r'Грузоотправител', text, flags=re.I)
        and re.search(r'Грузополучател', text, flags=re.I)
    )
    has_waybill_basis = bool(re.search(_waybill_basis_label_pattern(), text, flags=re.I))
    has_waybill_structure = (
        len(context["table_cells"]) >= 8
        and (context["header_box"] is not None or context["footer_box"] is not None or len(context["form_rois"]) >= 20)
        and (context["unp_hits"] >= 1 or has_waybill_parties)
    )
    if has_waybill_structure and (has_waybill_parties or has_waybill_basis):
        return "waybill"

    return None

# =========================
# dispatcher
# =========================

def detect_doc_type(path: Path):
    detected = _detect_doc_type_from_content(path)
    if detected:
        return detected

    p = path.name.lower()
    if "account_prot" in p:
        return "account_prot"
    if "invoice" in p:
        return "invoice"
    if "order" in p or "payment_order" in p:
        return "payment_order"
    if "waybill" in p or "наклад" in p:
        return "waybill"
    return None
