from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import (
    MONTHS_RU,
    clean_text,
    extract_company_names,
    extract_ru_date_text,
)


def _waybill_header_line_texts(header_lines):
    out = []
    if not header_lines:
        return out
    for line in header_lines:
        text = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
        if text:
            out.append(text)
    return out

def _waybill_basis_label_pattern():
    return r'(?:Основан|Сснован)\w*\s+\S*пуска'

def _waybill_title_from_text(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    if re.search(r'ТОВАРНО[-\s]*ТРАНСПОРТН\w*\s+НАКЛА\w+', cleaned, flags=re.I):
        return "ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ"
    if re.search(r'ТОВАРН\w*\s+НАКЛА\w+', cleaned, flags=re.I):
        return "ТОВАРНАЯ НАКЛАДНАЯ"
    return None

def _waybill_extract_header_date(header_text, line_texts):
    title_idx = 0
    for idx, line_text in enumerate(line_texts or []):
        if re.search(r'НАКЛА', line_text, flags=re.I):
            title_idx = idx
            break

    search_lines = (line_texts or [])[title_idx:title_idx + 6] or (line_texts or [])[:8]
    best = None
    for rel_idx, line_text in enumerate(search_lines):
        if re.search(r'\b(?:договор|основан|счет|сч[её]т|контракт)\b', line_text, flags=re.I):
            continue
        if re.search(r'\b(?:постановлен|министерств|экз\.)\b|30\.06\.2016|№\s*58', line_text, flags=re.I):
            continue
        candidate = extract_ru_date_text(line_text)
        if not candidate:
            continue
        score = (
            1 if rel_idx <= 2 else 0,
            1 if re.search(r'^\s*от\b', line_text, flags=re.I) else 0,
            1 if re.search(MONTHS_RU, line_text, flags=re.I) else 0,
            -rel_idx,
        )
        if best is None or score > best[0]:
            best = (score, candidate)

    if best:
        return clean_text(best[1])

    scope = clean_text(header_text)
    if scope:
        scope = re.split(
            r'Грузоотправитель\b|Грузополучатель\b|Заказчик автомобильной перевозки\b|Основан',
            scope,
            maxsplit=1,
            flags=re.I,
        )[0]
        candidate = extract_ru_date_text(scope)
        if candidate:
            return candidate

    return extract_ru_date_text(header_text)

def _waybill_cleanup_basis_value(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    cleaned = re.sub(r'^' + _waybill_basis_label_pattern() + r'[:\s-]*', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\(\s*[^)]*(?:наим|адрес|документ)[^)]*\)', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\(\s*[^)]*$', '', cleaned)
    cleaned = re.sub(
        r'\b(?:Пункт погрузки|Пункт разгрузки|Переадресовка|І\.\s*ТОВАРНЫЙ|I\.\s*ТОВАРНЫЙ|ТОВАРНЫЙ РАЗДЕЛ)\b.*$',
        '',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.;:-')
    if re.fullmatch(_waybill_basis_label_pattern(), cleaned, flags=re.I):
        return None
    return clean_text(cleaned)

def _waybill_is_basis_candidate(text):
    cleaned = _waybill_cleanup_basis_value(text)
    if not cleaned:
        return False
    if re.search(r'\b(?:грузоотправитель|грузополучатель|пункт погрузки|пункт разгрузки|переадресовка|товарный раздел)\b', cleaned, flags=re.I):
        return False
    if re.search(r'\b(?:договор|счет|сч[её]т|контракт|заявк|заказ|спецификац)\b', cleaned, flags=re.I):
        return True
    if '№' in cleaned and extract_ru_date_text(cleaned):
        return True
    return False

def _waybill_extract_basis(header_text, line_texts):
    for idx, line_text in enumerate(line_texts or []):
        match = re.search(_waybill_basis_label_pattern(), line_text, flags=re.I)
        if not match:
            continue

        trailing = _waybill_cleanup_basis_value(line_text[match.end():])
        if _waybill_is_basis_candidate(trailing):
            return trailing

        leading = _waybill_cleanup_basis_value(line_text[:match.start()])
        if _waybill_is_basis_candidate(leading):
            return leading

        for prev_idx in range(idx - 1, max(-1, idx - 3), -1):
            prev_line = _waybill_cleanup_basis_value(line_texts[prev_idx])
            if _waybill_is_basis_candidate(prev_line):
                return prev_line

        collected = []
        for next_line in line_texts[idx + 1:idx + 4]:
            if re.search(r'\b(?:Пункт погрузки|Пункт разгрузки|Переадресовка|ТОВАРНЫЙ РАЗДЕЛ)\b', next_line, flags=re.I):
                break
            candidate = _waybill_cleanup_basis_value(next_line)
            if _waybill_is_basis_candidate(candidate):
                collected.append(candidate)
                break
        if collected:
            return _waybill_cleanup_basis_value(" ".join(collected))

    match = re.search(
        _waybill_basis_label_pattern() + r'[:\s-]*(.+?)(?:І\.\s*ТОВАРНЫЙ|I\.\s*ТОВАРНЫЙ|ТОВАРНЫЙ РАЗДЕЛ|Пункт погрузки|Пункт разгрузки|Переадресовка|$)',
        header_text or '',
        flags=re.I,
    )
    if match:
        candidate = _waybill_cleanup_basis_value(match.group(1))
        if candidate:
            return candidate

    return None

def _waybill_collect_section(line_texts, start_anchor, end_anchors):
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

    section = clean_text(" ".join(parts))
    if not section:
        return None

    section = re.sub(r'\(\s*наименование,\s*адрес\s*\)', ' ', section, flags=re.I)
    section = re.sub(r'\(\s*наименование,\s*дата\s*и\s*номер\s*документа\s*\)', ' ', section, flags=re.I)
    return clean_text(section)

def _waybill_extract_between_anchors(text, start_anchor, end_anchors):
    if not text:
        return None

    start_match = re.search(start_anchor, text, flags=re.I)
    if not start_match:
        return None

    scope = text[start_match.start():]
    end = len(scope)
    tail = scope[start_match.end() - start_match.start():]
    for anchor in end_anchors:
        match = re.search(anchor, tail, flags=re.I)
        if match:
            end = min(end, start_match.end() - start_match.start() + match.start())

    section = clean_text(scope[:end])
    if not section:
        return None

    section = re.sub(r'\(\s*наименование,\s*адрес\s*\)', ' ', section, flags=re.I)
    section = re.sub(r'\(\s*наименование,\s*дата\s*и\s*номер\s*документа\s*\)', ' ', section, flags=re.I)
    return clean_text(section)

def _waybill_parse_party_section(section_text, label_pattern):
    out = {"name": None, "address": None}
    text = clean_text(section_text)
    if not text:
        return out

    payload = re.sub(r'^' + label_pattern + r'\s*:?\s*', '', text, flags=re.I)
    payload = clean_text(payload)
    if not payload:
        return out

    companies = extract_company_names(payload)
    if companies:
        out["name"] = clean_text(companies[0])

    if out["name"] and out["name"] in payload:
        address = payload.split(out["name"], 1)[1]
        address = re.sub(r'^\s*[,;:]\s*', '', address)
        out["address"] = clean_text(address)
    else:
        parts = [clean_text(part) for part in payload.split(",") if clean_text(part)]
        if len(parts) >= 2:
            out["name"] = out["name"] or parts[0]
            out["address"] = clean_text(", ".join(parts[1:]))

    return out

def parse_waybill_header(header_text, header_lines=None):
    out = {
        "document_type": None,
        "document_series": None,
        "document_number": None,
        "date": None,
        "sender": {"name": None, "address": None, "tax_id": None},
        "receiver": {"name": None, "address": None, "tax_id": None},
        "payer": {"name": None, "address": None, "tax_id": None},
        "basis": None,
    }
    line_texts = _waybill_header_line_texts(header_lines)
    basis_anchor = _waybill_basis_label_pattern()
    if not header_text:
        return out

    explicit_doc_type = _waybill_title_from_text(header_text)
    if explicit_doc_type:
        out["document_type"] = explicit_doc_type

    m = re.search(r'Серия\s+([A-ZА-Я]{1,4})', header_text)
    if m:
        out["document_series"] = clean_text(m.group(1))

    out["date"] = _waybill_extract_header_date(header_text, line_texts)

    m = re.search(r'Серия\s+[A-ZА-Я]{1,4}\s+([0-9]{4,10})', header_text)
    if m:
        out["document_number"] = clean_text(m.group(1))

    sender_section = _waybill_collect_section(
        line_texts,
        r'Грузоотправитель\b',
        (r'Грузополучатель\b', basis_anchor),
    ) or _waybill_extract_between_anchors(
        header_text,
        r'Грузоотправитель\b',
        (r'Грузополучатель\b', basis_anchor),
    )
    receiver_section = _waybill_collect_section(
        line_texts,
        r'Грузополучатель\b',
        (basis_anchor,),
    ) or _waybill_extract_between_anchors(
        header_text,
        r'Грузополучатель\b',
        (basis_anchor,),
    )

    sender_vals = _waybill_parse_party_section(sender_section, r'Грузоотправитель\b')
    receiver_vals = _waybill_parse_party_section(receiver_section, r'Грузополучатель\b')
    for field, value in sender_vals.items():
        if value:
            out["sender"][field] = value
    for field, value in receiver_vals.items():
        if value:
            out["receiver"][field] = value

    out["basis"] = _waybill_extract_basis(header_text, line_texts)

    return out
