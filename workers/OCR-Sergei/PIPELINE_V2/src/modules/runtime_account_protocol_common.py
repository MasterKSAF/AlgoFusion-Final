from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import (
    MONTHS_RU,
    clean_text,
    cleanup_bank_name,
    extract_all_accounts,
    extract_all_bics,
    extract_all_tax_ids,
    normalize_account,
)


def _account_prot_normalize_unit(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    normalized = cleaned.lower().replace(".", "").replace("τ", "т").strip()
    if normalized in {"шт", "шп"}:
        return "шт"
    return cleaned

def split_supplier_customer(header_text):
    if not header_text:
        return None, None
    m = re.search(r'Покупатель', header_text, flags=re.I)
    if not m:
        return header_text, None
    return clean_text(header_text[:m.start()]), clean_text(header_text[m.start():])

def extract_contract(header_text):
    out = {"contract_number": None, "contract_date": None, "contract_type": None}
    if not header_text:
        return out

    m = re.search(
        r'Основание:\s*([А-Яа-яA-Za-z ]+?)\s*№\s*([A-Za-z0-9\-\/]+)\s*от\s*([0-3]?\d\.[01]?\d\.20\d{2})',
        header_text,
        flags=re.I,
    )
    if m:
        out["contract_type"] = clean_text(m.group(1))
        out["contract_number"] = clean_text(m.group(2))
        out["contract_date"] = clean_text(m.group(3))
    return out

def _account_prot_header_sort_key(region):
    bbox = region.get("bbox") or [0, 0, 0, 0]
    return (round(bbox[1] / 15), bbox[1], bbox[0])

def _account_prot_join_region_texts(regions):
    parts = [clean_text(region.get("text")) for region in regions]
    parts = [part for part in parts if part]
    return clean_text(" ".join(parts))

def _account_prot_header_views(regions):
    header_box = next((region for region in regions if region.get("id") == "header_box"), None)
    header_box_text = clean_text(header_box.get("text")) if header_box else None
    header_rois = sorted(
        [
            region
            for region in regions
            if region.get("kind") == "header_form_roi" and clean_text(region.get("text"))
        ],
        key=_account_prot_header_sort_key,
    )
    header_form_text = _account_prot_join_region_texts(header_rois)
    combined_text = clean_text(" ".join(part for part in [header_form_text, header_box_text] if part))
    return {
        "header_box_text": header_box_text,
        "header_form_text": header_form_text,
        "header_text": header_form_text or header_box_text,
        "combined_text": combined_text,
    }

def _account_prot_trim_by_stop_words(text, stop_patterns):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cut_at = len(cleaned)
    for pattern in stop_patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            cut_at = min(cut_at, match.start())
    return clean_text(cleaned[:cut_at])

def _account_prot_normalize_address(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'(?<=,\s)(?:[bBбБ]|6)(?:[aAаА])\b', '6а', cleaned)
    cleaned = re.sub(r'(?<=\s)(?:[bBбБ]|6)(?:[aAаА])\b', '6а', cleaned)
    cleaned = re.sub(r',(?=\S)', ', ', cleaned)
    cleaned = re.sub(r'\s+,', ',', cleaned)
    cleaned = re.sub(r'(?i)\b(г\.|д\.|ул\.|пр\.)\s*(?=\S)', lambda m: m.group(1) + ' ', cleaned)
    return clean_text(cleaned)

def _account_prot_cleanup_company_name(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'^\s*Поставщик(?:\s+и\s+его\s+адрес:?)?\s*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'^\s*Покупатель(?:\s+и\s+его\s+адрес:?)?\s*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\bСЧЕТ[-\s]*ПРОТОКОЛ\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bего\s+адрес:?\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return cleaned or None

def _account_prot_cleanup_bank_name(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'\b[A-Z]{6}[A-Z0-9]{2}\b', ' ', cleaned)
    cleaned = re.sub(r'\bтовары\s*\(продукцию\)\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bсогласования\b.*$', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return cleaned or None

def _account_prot_extract_document_number_and_date(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None, None
    scope = cleaned
    title_match = re.search(r'счет[-\s]*протокол', cleaned, flags=re.I)
    if title_match:
        scope = cleaned[title_match.start():]
    pattern = re.compile(
        r'№\s*([A-Za-zА-Яа-я0-9\-/]+)\s*от\s*([0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2}\s*г?\.?)',
        flags=re.I,
    )
    for match in pattern.finditer(scope):
        candidate = clean_text(match.group(1))
        normalized = normalize_account(candidate)
        if not candidate or (normalized and normalized.startswith("BY")):
            continue
        return candidate, clean_text(match.group(2))
    return None, None

def _account_prot_extract_bic_after_label(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    patterns = [
        r'\bBIC\b\s*[:\-]?\s*([A-Za-zА-Яа-яІіҮү0-9]{8,12})',
        r'\bБИК\b\s*[:\-]?\s*([A-Za-zА-Яа-яІіҮү0-9]{8,12})',
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if not match:
            continue

        raw_value = clean_text(match.group(1))
        if not raw_value:
            continue

        normalized = normalize_account(raw_value)
        if not normalized:
            continue

        bic_match = re.search(r'[A-Z]{6}[A-Z0-9]{2}', normalized)
        if bic_match:
            return bic_match.group(0)

        if len(normalized) >= 8:
            return normalized[:8]

    return None
