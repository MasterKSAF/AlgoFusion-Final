from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import clean_text, extract_all_tax_ids, extract_tax_id
from src.modules.runtime_invoice_header_party_helpers import (
    _invoice_clean_party_address,
    _invoice_collect_section,
    _invoice_collect_section_from_raw,
    _invoice_extract_between_anchors,
    _invoice_extract_company_match,
    _invoice_extract_overflow_party,
    _invoice_extract_party_chunks,
    _invoice_extract_postal_prefix,
    _invoice_is_plausible_party_address,
    _invoice_is_plausible_party_name,
    _invoice_recover_split_customer_name,
    _invoice_score_parsed_party,
    _invoice_strip_inline_anchors,
    _invoice_strip_markup,
    _invoice_trim_to_first_party,
)
from src.modules.runtime_invoice_header_text import extract_phone_pretty


def _invoice_parse_supplier_section(line_texts, header_text=None, raw_ocr_items=None):
    def _parse_supplier_text(section_text):
        out = {"name": None, "tax_id": None, "address": None}
        text = _invoice_strip_markup(section_text)
        if not text:
            return out

        payload = re.sub(r'^.*?Поставщик:\s*', '', text, flags=re.I)
        payload = _invoice_strip_inline_anchors(payload)
        payload = clean_text(payload)
        company_name, company_span = _invoice_extract_company_match(payload or text)
        if company_name:
            out["name"] = company_name

        out["tax_id"] = extract_tax_id(text)
        if not out["tax_id"]:
            tax_ids = extract_all_tax_ids(text)
            if tax_ids:
                out["tax_id"] = tax_ids[0]

        address_source = None
        if company_span and payload:
            address_source = payload[company_span[1]:]
        elif out["name"] and payload and out["name"] in payload:
            address_source = payload.split(out["name"], 1)[1]
        elif payload:
            address_source = payload

        address = _invoice_clean_party_address(address_source)
        postal_prefix = _invoice_extract_postal_prefix(text, payload, address)
        if address and postal_prefix and not re.match(r'^\s*' + re.escape(postal_prefix) + r'(?:\b|,)', address):
            address = clean_text(f"{postal_prefix}, {address}")
        if _invoice_is_plausible_party_address(address):
            out["address"] = address

        if not _invoice_is_plausible_party_name(out.get("name")):
            out["name"] = None
        return out

    org_section = _invoice_collect_section(
        line_texts,
        r'Организация:',
        (r'Счет\s*№', r'УНП\b', r'Поставщик:', r'Покупатель:', r'Основание:'),
    )
    supplier_meta_section = _invoice_collect_section(
        line_texts,
        r'УНП\s*\d{9}',
        (r'Поставщик:', r'Покупатель:', r'Основание:'),
    )
    supplier_address_section = _invoice_collect_section(
        line_texts,
        r'Поставщик:',
        (r'Покупатель:', r'Основание:'),
    )
    fallback_section = _invoice_extract_between_anchors(
        header_text,
        r'Поставщик:',
        (r'Покупатель:', r'Основание:', r'Счет\s*№', r'Организация:'),
    )
    raw_section = _invoice_collect_section_from_raw(
        raw_ocr_items,
        r'Поставщик:',
        (r'Покупатель:', r'Основание:', r'Счет\s*№', r'Организация:'),
    )

    combined = clean_text(" ".join(
        part for part in [
            _invoice_strip_inline_anchors(org_section),
            _invoice_strip_inline_anchors(supplier_meta_section),
            _invoice_strip_inline_anchors(supplier_address_section),
        ]
        if part
    ))

    primary_candidates = [org_section, supplier_address_section, fallback_section, raw_section]
    primary_seen = set()
    for candidate in primary_candidates:
        cleaned_candidate = _invoice_trim_to_first_party(candidate)
        if not cleaned_candidate:
            continue
        key = cleaned_candidate.lower()
        if key in primary_seen:
            continue
        primary_seen.add(key)
        parsed = _parse_supplier_text(cleaned_candidate)
        if parsed.get("name") or parsed.get("address") or parsed.get("tax_id"):
            return parsed

    candidates = [combined, supplier_meta_section]
    best = None
    seen = set()
    for candidate in candidates:
        cleaned_candidate = _invoice_trim_to_first_party(candidate)
        if not cleaned_candidate:
            continue
        key = cleaned_candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed = _parse_supplier_text(cleaned_candidate)
        score = _invoice_score_parsed_party(parsed, "supplier", cleaned_candidate)
        if best is None or score > best[0]:
            best = (score, parsed)

    return best[1] if best else {"name": None, "tax_id": None, "address": None}

def _invoice_parse_customer_section(line_texts, header_text=None, raw_ocr_items=None):
    def _parse_customer_text(section_text):
        out = {"name": None, "address": None, "tax_id": None, "kpp": None, "phone": None}
        text = _invoice_strip_markup(section_text)
        if not text:
            return out

        out["phone"] = extract_phone_pretty(text)

        tax_match = re.search(r'УНП\s*(\d{9})', text, flags=re.I)
        if tax_match:
            out["tax_id"] = clean_text(tax_match.group(1))

        kpp_match = re.search(r'КПП\s*(\d{9})', text, flags=re.I)
        if kpp_match:
            out["kpp"] = clean_text(kpp_match.group(1))

        payload = re.sub(r'^.*?Покупатель:\s*', '', text, flags=re.I)
        payload = re.sub(r'\bУНП\s*\d{9}\b\s*,?\s*', ' ', payload, flags=re.I)
        payload = re.sub(r'\bКПП\s*\d{9}\b\s*,?\s*', ' ', payload, flags=re.I)
        payload = _invoice_strip_inline_anchors(payload)
        payload = clean_text(payload)

        company_name, company_span = _invoice_extract_company_match(payload or text)
        address_source = payload

        if not company_name:
            recovered_name, recovered_address_source = _invoice_recover_split_customer_name(payload)
            if recovered_name:
                company_name = recovered_name
                company_span = None
                address_source = recovered_address_source

        if company_name and _invoice_is_plausible_party_name(company_name):
            out["name"] = company_name

        if company_span and payload:
            address_source = payload[company_span[1]:]
        elif address_source and out["name"] and out["name"] in address_source:
            split_pos = address_source.rfind(out["name"])
            address_source = address_source[split_pos + len(out["name"]):]

        if address_source and out["name"]:
            last_token = re.split(r'\s+', out["name"])[-1].strip('"«»')
            if last_token:
                address_source = re.sub(
                    r'^\s*' + re.escape(last_token) + r'["»]?\s*,\s*',
                    '',
                    address_source,
                    flags=re.I,
                )

        address = _invoice_clean_party_address(address_source)
        if _invoice_is_plausible_party_address(address):
            out["address"] = address

        if not _invoice_is_plausible_party_name(out.get("name")):
            out["name"] = None
        return out

    customer_section = _invoice_collect_section(
        line_texts,
        r'Покупатель:',
        (r'Основание:', r'Счет\s*№', r'Организация:'),
    )
    fallback_section = _invoice_extract_between_anchors(
        header_text,
        r'Покупатель:',
        (r'Основание:', r'Счет\s*№', r'Организация:'),
    )
    raw_section = _invoice_collect_section_from_raw(
        raw_ocr_items,
        r'Покупатель:',
        (r'Основание:', r'Счет\s*№', r'Организация:'),
    )
    supplier_section = _invoice_collect_section(
        line_texts,
        r'Поставщик:',
        (r'Покупатель:', r'Основание:'),
    )
    supplier_fallback_section = _invoice_extract_between_anchors(
        header_text,
        r'Поставщик:',
        (r'Покупатель:', r'Основание:', r'Счет\s*№', r'Организация:'),
    )
    supplier_raw_section = _invoice_collect_section_from_raw(
        raw_ocr_items,
        r'Поставщик:',
        (r'Покупатель:', r'Основание:', r'Счет\s*№', r'Организация:'),
    )

    overflow_candidates = [
        _invoice_extract_overflow_party(supplier_raw_section),
        _invoice_extract_overflow_party(supplier_fallback_section),
        _invoice_extract_overflow_party(supplier_section),
    ]

    chunk_candidates = []
    for source in [supplier_raw_section, supplier_fallback_section, supplier_section, raw_section, fallback_section, header_text]:
        chunks = _invoice_extract_party_chunks(source)
        if len(chunks) >= 2:
            chunk_candidates.extend(chunks[1:])

    candidates = []
    seen = set()
    for idx, candidate in enumerate([*chunk_candidates, raw_section, fallback_section, customer_section, *overflow_candidates]):
        cleaned_candidate = _invoice_strip_markup(candidate)
        if not cleaned_candidate:
            continue
        key = cleaned_candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed = _parse_customer_text(cleaned_candidate)
        score = _invoice_score_parsed_party(parsed, "customer", cleaned_candidate)
        candidates.append({
            "index": idx,
            "source": cleaned_candidate,
            "score": score,
            "parsed": parsed,
        })

    if not candidates:
        return {"name": None, "address": None, "tax_id": None, "kpp": None, "phone": None}

    def _pick_field(field):
        best = None
        for candidate in candidates:
            value = candidate["parsed"].get(field)
            if not value:
                continue
            score = candidate["score"]
            if field == "name":
                if not _invoice_is_plausible_party_name(value):
                    continue
            elif field == "address":
                value = _invoice_clean_party_address(value)
                if not _invoice_is_plausible_party_address(value):
                    continue
            if best is None or (score, -candidate["index"]) > (best[0], -best[1]):
                best = (score, candidate["index"], value)
        return best[2] if best else None

    out = {"name": None, "address": None, "tax_id": None, "kpp": None, "phone": None}
    out["name"] = _pick_field("name")
    out["address"] = _pick_field("address")

    ordered = sorted(candidates, key=lambda item: (item["score"], -item["index"]), reverse=True)
    for field in ("tax_id", "kpp", "phone"):
        for candidate in ordered:
            value = candidate["parsed"].get(field)
            if value:
                out[field] = value
                break

    return out
