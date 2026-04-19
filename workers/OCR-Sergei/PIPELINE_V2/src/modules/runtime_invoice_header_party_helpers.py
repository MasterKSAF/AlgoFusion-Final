from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import clean_text, extract_company_names


def _invoice_header_line_texts(header_lines):
    out = []
    if not header_lines:
        return out
    for line in header_lines:
        txt = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
        if txt:
            out.append(txt)
    return out

def _invoice_collect_section(line_texts, start_anchor, end_anchors):
    if not line_texts:
        return None

    start_idx = None
    start_pos = 0
    start_at_line_begin = re.compile(r'^\s*' + start_anchor, flags=re.I)
    start_anywhere = re.compile(start_anchor, flags=re.I)

    for idx, line_text in enumerate(line_texts):
        match = start_at_line_begin.search(line_text)
        if match:
            start_idx = idx
            start_pos = match.start()
            break

    if start_idx is None:
        for idx, line_text in enumerate(line_texts):
            match = start_anywhere.search(line_text)
            if match:
                start_idx = idx
                start_pos = match.start()
                break

    if start_idx is None:
        return None

    parts = []
    for idx in range(start_idx, len(line_texts)):
        line_text = line_texts[idx]
        if idx == start_idx and start_pos:
            line_text = line_text[start_pos:]

        if idx > start_idx and any(re.search(anchor, line_text, flags=re.I) for anchor in end_anchors):
            break

        parts.append(line_text)

    return clean_text(" ".join(parts))

def _invoice_extract_between_anchors(text, start_anchor, end_anchors):
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

def _invoice_extract_postal_prefix(*sources):
    for source in sources:
        text = clean_text(source)
        if not text:
            continue
        match = re.search(r'(?:^|,\s*)(\d{6})(?=,|$)', text)
        if match:
            return match.group(1)
    return None

def _invoice_strip_markup(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'<\s*br\s*/?\s*>', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'</?(?:b|u|i|em|strong|span|div|p)[^>]*>', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    return clean_text(cleaned)

def _invoice_has_markup(text):
    return bool(text and re.search(r'<[^>]+>', str(text)))

def _invoice_strip_inline_anchors(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return None
    cleaned = re.sub(
        r'(?:(?<=^)|(?<=[\s,;:"«»]))(?:Поставщик|Покупатель|Основание|Организация)\s*:?\s*',
        ' ',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'\(\s*наименование.*?\)', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s+([,;:])', r'\1', cleaned)
    return clean_text(cleaned)

def _invoice_count_company_mentions(text):
    cleaned = _invoice_strip_inline_anchors(text)
    if not cleaned:
        return 0
    return len(extract_company_names(cleaned))

def _invoice_is_plausible_party_name(text):
    cleaned = _invoice_strip_inline_anchors(text)
    if not cleaned:
        return False
    if re.search(r'\b(?:Поставщик|Покупатель|Основание|Организация|тел\.?|УНП|КПП|БИК|р/с|в банке)\b', cleaned, flags=re.I):
        return False
    if ':' in cleaned and not re.search(r'["«»]', cleaned):
        return False
    if re.search(r'\b\+375\b', cleaned):
        return False
    if extract_company_names(cleaned):
        return True
    partial_patterns = [
        r'^(?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+["»]?$',
        r'^(?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+["»]?$',
    ]
    return any(re.fullmatch(pattern, cleaned, flags=re.I) for pattern in partial_patterns)

def _invoice_is_plausible_party_address(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return False
    if cleaned.startswith(','):
        return False
    if re.search(r'\b(?:Поставщик|Покупатель|Основание|Организация|УНП|УПП|КПП|БИК|р/с|в банке|тел\.?)\b', cleaned, flags=re.I):
        return False
    if _invoice_count_company_mentions(cleaned) > 0:
        return False
    if len(cleaned) < 10:
        return False
    return bool(re.search(r'\b(?:Беларусь|Минск|обл\.?|район|р-н|ул\.?|пр\.?|д\.?|дом|пом\.?|оф\.?|каб\.?|корп\.?|индекс|\d{6})\b', cleaned, flags=re.I))

def _invoice_clean_party_address(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'^\s*[,;:]+\s*', '', cleaned)
    cleaned = re.sub(r'\b(?:УНП|УПП|КПП)\s*\d{9}\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bтел\.?\s*:?.*$', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bр/с\b.*$', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\bв банке\b.*$', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'^(\d{6})\s*,\s*\1\b', r'\1', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s+([,;:])', r'\1', cleaned)
    cleaned = cleaned.strip(' ,;:')
    return clean_text(cleaned)

def _invoice_extract_company_match(text):
    cleaned = _invoice_strip_inline_anchors(text)
    if not cleaned:
        return None, None

    patterns = [
        r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+["»])',
        r'((?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+["»])',
    ]

    best = None
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.I):
            candidate = clean_text(match.group(1))
            if not _invoice_is_plausible_party_name(candidate):
                continue
            score = (len(candidate), -match.start())
            if best is None or score > best[0]:
                best = (score, candidate, match.span(1))

    if not best:
        return None, None
    return best[1], best[2]

def _invoice_recover_split_customer_name(text):
    cleaned = _invoice_strip_inline_anchors(text)
    if not cleaned:
        return None, None

    leading = re.match(r'\s*([^,]{2,40}["»])\s*,\s*(.+)$', cleaned)
    trailing = re.search(
        r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+|(?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+)$',
        cleaned,
        flags=re.I,
    )
    if not leading or not trailing:
        return None, None

    leading_part = clean_text(leading.group(1))
    trailing_part = clean_text(trailing.group(1))
    if not leading_part or not trailing_part:
        return None, None

    cleaned_leading_part = clean_text(re.sub(r'["»]+$', '', leading_part))
    rebuilt = clean_text(f'{trailing_part} {cleaned_leading_part}"')
    if not _invoice_is_plausible_party_name(rebuilt):
        return None, None

    return rebuilt, clean_text(leading.group(2))

def _invoice_collect_section_from_raw(raw_ocr_items, start_anchor, end_anchors):
    if not raw_ocr_items:
        return None

    prepared = []
    for item in raw_ocr_items:
        text = _invoice_strip_markup(item.get("text"))
        bbox = item.get("bbox") or [0, 0, 0, 0]
        if text:
            prepared.append((bbox, text))

    if not prepared:
        return None

    start_matches = []
    for bbox, text in prepared:
        match = re.search(start_anchor, text, flags=re.I)
        if match:
            start_matches.append((bbox, text, match))

    if not start_matches:
        return None

    start_bbox, _start_text, _start_match = min(start_matches, key=lambda item: (item[0][1], item[0][0]))
    start_y = start_bbox[1]

    end_y = None
    for bbox, text in prepared:
        if bbox[1] < start_y - 5:
            continue
        if any(re.search(anchor, text, flags=re.I) for anchor in end_anchors):
            if end_y is None or bbox[1] < end_y:
                end_y = bbox[1]

    section_items = []
    for bbox, text in prepared:
        if bbox[1] < start_y - 20:
            continue
        if end_y is not None and bbox[1] >= end_y:
            continue
        match = re.search(start_anchor, text, flags=re.I)
        if match:
            text = clean_text(text[match.start():])
        section_items.append((round(bbox[1] / 12), bbox[1], bbox[0], text))

    section_items.sort(key=lambda item: (item[0], item[2], item[1]))
    joined = clean_text(" ".join(text for _band, _y, _x, text in section_items if text))
    return _invoice_extract_between_anchors(joined, start_anchor, end_anchors) or joined

def _invoice_find_party_chunk_starts(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return []

    tax_starts = [m.start() for m in re.finditer(r"\bУНП\s*\d{9}\b", cleaned, flags=re.I)]
    if len(tax_starts) >= 2:
        return tax_starts

    company_starts = []
    patterns = [
        r'((?:ООО|ОАО|ЗАО|ОДО|ЧУП)\s*["«][^"»]+["»])',
        r'((?:Общество с ограниченной ответственностью|Открытое акционерное общество|Закрытое акционерное общество)\s*["«][^"»]+["»])',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.I):
            company_starts.append(match.start(1))

    return sorted(set(company_starts))

def _invoice_trim_to_first_party(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return None

    starts = _invoice_find_party_chunk_starts(cleaned)
    if len(starts) >= 2:
        return clean_text(cleaned[:starts[1]])
    return cleaned

def _invoice_extract_overflow_party(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return None

    starts = _invoice_find_party_chunk_starts(cleaned)
    if len(starts) >= 2:
        return clean_text(cleaned[starts[1]:])
    return None

def _invoice_extract_party_chunks(text):
    cleaned = _invoice_strip_markup(text)
    if not cleaned:
        return []

    starts = _invoice_find_party_chunk_starts(cleaned)
    if not starts:
        return []

    starts = sorted(set(starts))
    ends = starts[1:] + [len(cleaned)]
    out = []
    seen = set()
    for start, end in zip(starts, ends):
        chunk = clean_text(cleaned[start:end])
        if not chunk:
            continue
        key = chunk.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(chunk)
    return out

def _invoice_score_parsed_party(out, role, source_text):
    score = 0
    if out.get("name"):
        score += 6 if _invoice_is_plausible_party_name(out["name"]) else -6
    if out.get("address"):
        score += 5 if _invoice_is_plausible_party_address(out["address"]) else -5
    if out.get("tax_id"):
        score += 1
    if role == "customer" and out.get("kpp"):
        score += 1
    if role == "customer" and out.get("phone"):
        score += 1

    cleaned_source = _invoice_strip_markup(source_text)
    if cleaned_source:
        if role == "supplier" and re.search(r'\bПокупатель\b', cleaned_source, flags=re.I):
            score -= 2
        if role == "customer" and re.search(r'\b(?:Поставщик|Организация)\b', cleaned_source, flags=re.I):
            score -= 2
        if _invoice_count_company_mentions(cleaned_source) > 1:
            score -= 2
        if _invoice_has_markup(source_text):
            score -= 1

    return score
