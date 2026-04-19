from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    choose_best_code_prefixed_text,
    clean_text,
    cleanup_bank_name,
    extract_all_accounts,
    extract_all_bics,
    extract_all_datetimes,
    extract_all_tax_ids,
    extract_bank_account,
    extract_company_names,
    extract_person_name,
    get_regions,
    load_json,
    normalize_leading_code_prefix,
    row_texts,
    to_float,
)
from src.modules.runtime_payment_order_helpers import (
    build_form_text_map,
    enrich_payment_order_result,
    extract_all_po_bics,
    find_first,
    normalize_po_bank_name,
    strip_po_markup,
)

def roi_text(roi):
    return strip_po_markup(roi.get("text"))

def y_overlap_len(a, b):
    return max(0, min(a[3], b[3]) - max(a[1], b[1]))

def trim_at_anchors(text, anchors):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    cut_at = len(cleaned)
    for anchor in anchors:
        m = re.search(anchor, cleaned, flags=re.I)
        if m:
            cut_at = min(cut_at, m.start())

    return clean_text(cleaned[:cut_at])

def extract_form_section(text, start_anchor, end_anchors):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    start_match = re.search(start_anchor, cleaned, flags=re.I)
    if not start_match:
        return None

    scope = cleaned[start_match.start():]
    cut_at = len(scope)
    tail = scope[start_match.end() - start_match.start():]
    for anchor in end_anchors:
        match = re.search(anchor, tail, flags=re.I)
        if match:
            cut_at = min(cut_at, start_match.end() - start_match.start() + match.start())

    return clean_text(scope[:cut_at])

def extract_section_bank_name(section_text, label_pattern):
    cleaned = clean_text(section_text)
    if not cleaned:
        return None
    m = re.search(label_pattern + r':?\s*(.+?)(?=\s+Счет\s*№|\s+Код\s+банка:|$)', cleaned, flags=re.I)
    return normalize_po_bank_name(m.group(1)) if m else None

def split_company_and_address(text):
    payload = clean_text(text)
    if not payload:
        return None, None

    companies = extract_company_names(payload)
    if companies:
        company = clean_text(companies[0])
        tail = clean_text(payload.split(company, 1)[1]) if company in payload else None
        if tail:
            tail = re.sub(r'^\s*[,;:]\s*', '', tail)
            tail = clean_text(tail)
        return company, tail

    m = re.match(r'(.+?)\s+((?:\d{6}|Г\.|ГОР\.|РЕСПУБЛИКА|БЕЛАРУСЬ).+)$', payload, flags=re.I)
    if m:
        return clean_text(m.group(1)), clean_text(m.group(2))

    return payload, None

def extract_money_words(text):
    cleaned = trim_at_anchors(
        text,
        (
            r'Плательщик:',
            r'Код\s+валюты:',
            r'Сумма\s+цифрами:',
            r'Банк-отправитель:',
        ),
    )
    if not cleaned:
        return None

    m = re.search(
        r'([А-ЯЁа-яё\-\s]+рубл[а-яё]+,?\s*\d{1,2}\s*коп[а-яё]+)',
        cleaned,
        flags=re.I,
    )
    return clean_text(m.group(1)) if m else cleaned

def extract_money_words_from_raw(raw_items):
    for item in raw_items:
        text = clean_text(item.get("text"))
        bbox = item.get("bbox") or [0, 0, 0, 0]
        if not text:
            continue
        if bbox[1] > 420 or bbox[3] < 240:
            continue
        if not re.search(r'Сумма\s+и\s+валюта:', text, flags=re.I):
            continue
        if not re.search(r'рубл', text, flags=re.I):
            continue
        text = re.sub(r'^\s*Сумма\s+и\s+валюта:\s*', '', text, flags=re.I)
        return extract_money_words(text)
    return None

def cleanup_po_field(text, stop_patterns=()):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cut_at = len(cleaned)
    for pattern in stop_patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            cut_at = min(cut_at, match.start())
    cleaned = clean_text(cleaned[:cut_at])
    return cleaned

def normalize_po_company_name(text):
    cleaned = cleanup_po_field(
        text,
        (
            r'\bКод\s+банка\b',
            r'\bНазначение\s+платежа\b',
            r'\bСчет\s*№\b',
            r'\b№\s*документа\b',
            r'\bДата\s+документа\b',
            r'\bУполномоченный\s+орган\b',
        ),
    )
    if not cleaned:
        return None

    companies = extract_company_names(cleaned)
    if companies:
        return clean_text(companies[0])

    partial_patterns = [
        r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+)',
        r'((?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+)',
    ]
    for pattern in partial_patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            candidate = clean_text(match.group(1))
            if candidate and candidate.count('"') % 2 == 1:
                candidate = candidate + '"'
            elif candidate and candidate.count('«') > candidate.count('»'):
                candidate = candidate + '»'
            return candidate

    return cleaned

def normalize_po_bank_name(text):
    cleaned = cleanup_po_field(
        text,
        (
            r'\bСчет\s*№\b',
            r'\bКод\s+банка\b',
            r'\bПодпись\s+исполнителя\s+банка\b',
            r'\bДата\s+поступления\b',
            r'\bДата\s+исполнения\b',
            r'\bШтамп\s+банка\b',
            r'\bНазначение\s+платежа\b',
            r'\b№\s*документа\b',
            r'\bУНП\b',
            r'\bОчередь\b',
        ),
    )
    if not cleaned:
        return None
    cleaned = cleanup_bank_name(cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return clean_text(cleaned)

def extract_purpose_candidates_from_raw(raw_items):
    out = []
    for item in raw_items:
        text = clean_text(item.get("text"))
        if not text:
            continue
        match = re.search(r'\u041d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u043f\u043b\u0430\u0442\u0435\u0436\u0430:\s*(.+)$', text, flags=re.I)
        if match:
            value = clean_text(match.group(1))
            if value:
                out.append(value)
    return out
