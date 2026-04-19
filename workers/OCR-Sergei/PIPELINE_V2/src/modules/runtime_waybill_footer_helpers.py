from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    MONTHS_RU,
    clean_text,
    extract_company_names,
    extract_ru_date_text,
    get_regions,
    group_rows,
    is_index_row,
    load_json,
    normalize_percent,
    row_texts,
    to_float,
    to_int,
)

# =========================
# Waybill
# =========================

def extract_waybill_numeric_totals(table_rows):
    totals = {
        "quantity_total": None,
        "cost_total": None,
        "vat_total": None,
        "cost_with_vat_total": None,
        "vat_total_words": None,
        "cost_with_vat_total_words": None,
    }

    for row in table_rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "итого" not in joined:
            continue

        totals["quantity_total"] = to_int(texts[2]) if len(texts) > 2 else None
        totals["cost_total"] = to_float(texts[4]) if len(texts) > 4 else None
        totals["vat_total"] = to_float(texts[6]) if len(texts) > 6 else None

        if len(texts) > 7:
            m = re.search(r'([0-9]+[.,][0-9]{2})', texts[7] or "")
            totals["cost_with_vat_total"] = to_float(m.group(1)) if m else to_float(texts[7])

        break

    return totals

def extract_waybill_total_words(footer_lines, anchor):
    if not footer_lines:
        return None

    for line in footer_lines:
        line_text = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
        if not line_text:
            continue

        m = re.search(rf'{anchor}\s+(.+)', line_text, flags=re.I)
        if m:
            return clean_text(m.group(1))

    return None

def _waybill_footer_line_texts(footer_lines):
    out = []
    if not footer_lines:
        return out
    for line in footer_lines:
        text = clean_text(line.get("text")) if isinstance(line, dict) else clean_text(line)
        if text:
            out.append(text)
    return out


def _waybill_cleanup_footer_phrase(text, mode=None):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+([,.;:])', r'\1', cleaned)
    cleaned = re.sub(r'^(?:<br>\s*)+', '', cleaned, flags=re.I)

    if mode == "released_by":
        cleaned = re.sub(r'^Отпуск разрешил\s*', '', cleaned, flags=re.I)
        cleaned = re.sub(r'^[,.;:!?-]+\s*', '', cleaned)
        return clean_text(cleaned)

    if mode == "handed_by":
        cleaned = re.sub(r'^Сдал грузоотправитель\s*', '', cleaned, flags=re.I)
        cleaned = re.sub(r'^[,.;:!?-]+\s*', '', cleaned)
        return clean_text(cleaned)

    if mode == "accepted_for_delivery":
        cleaned = re.sub(r'^Товар к (?:доставке|перевозке) принял[.:\-]?\s*', '', cleaned, flags=re.I)
        cleaned = re.sub(r'\s+по доверенности\b.*$', '', cleaned, flags=re.I)
        cleaned = re.sub(r'\s+выданной\b.*$', '', cleaned, flags=re.I)
        cleaned = re.sub(r'\s+наименование организации\b.*$', '', cleaned, flags=re.I)
        cleaned = re.sub(r'^[,.;:!?-]+\s*', '', cleaned)
        return clean_text(cleaned)

    if mode == "received_by":
        cleaned = re.sub(r'^Принял грузополучатель\s*', '', cleaned, flags=re.I)
        cleaned = re.sub(r'^(?:<br>\s*)+', '', cleaned, flags=re.I)
        cleaned = clean_text(cleaned)
        if cleaned and re.match(r'^(РУП|УП|Издательство)\b', cleaned, flags=re.I):
            return None
        return cleaned or None

    if mode == "documents":
        cleaned = re.sub(r'^С товаром (?:переданы|нервданы)\s+документы:?\s*', '', cleaned, flags=re.I)
        cleaned = clean_text(cleaned)
        if not cleaned:
            return None
        if re.match(r'^(РУП|УП|Издательство)\b', cleaned, flags=re.I):
            return None
        return cleaned

    if mode == "publisher":
        cleaned = re.sub(r'\s*Внимание!.*$', '', cleaned, flags=re.I)
        return clean_text(cleaned)

    return cleaned


def _waybill_collect_footer_phrase(line_texts, anchor_pattern, stop_patterns=(), mode=None):
    if not line_texts:
        return None

    collected = []
    started = False

    for line_text in line_texts:
        if not started:
            match = re.search(anchor_pattern, line_text, flags=re.I)
            if not match:
                continue
            collected.append(clean_text(line_text[match.start():]))
            started = True
            continue

        if any(re.search(pattern, line_text, flags=re.I) for pattern in stop_patterns):
            break
        if re.match(r'^\s*\(', line_text):
            continue
        if re.match(r'^\s*(РУП|УП|Внимание!)', line_text, flags=re.I):
            break
        if re.match(r'^\s*(по доверенности|выданной|наименование организации)', line_text, flags=re.I):
            break
        break

    return _waybill_cleanup_footer_phrase(" ".join(part for part in collected if part), mode=mode)


def _waybill_normalize_country_tail(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    italy = ''.join(chr(x) for x in (1048, 1090, 1072, 1083, 1080, 1103))
    italy_tail = f'/{italy}/'
    lowered = cleaned.lower().replace(' ', '')
    if lowered.endswith(italy_tail.lower()):
        cleaned = re.sub(r'\s*/\s*[^/]+\s*/\s*$', f' {italy_tail}', cleaned)
        return clean_text(cleaned)

    tokens = cleaned.split()
    if italy_tail not in cleaned and len(tokens) >= 3:
        last = tokens[-1].strip(' ,.;:/\\')
        prev = tokens[-2].strip(' ,.;:/\\')
        prev2 = tokens[-3].strip(' ,.;:/\\')
        last_letters = ''.join(ch for ch in last if ch.isalpha())
        prev_letters = ''.join(ch for ch in prev if ch.isalpha())
        latin = sum('a' <= ch.lower() <= 'z' for ch in last_letters)
        cyr = sum(('а' <= ch.lower() <= 'я') or ch.lower() == 'ё' for ch in last_letters)
        if (
            any(ch.isdigit() for ch in prev2)
            and 1 <= len(prev_letters) <= 3
            and 5 <= len(last_letters) <= 14
            and (latin >= cyr or latin >= 3)
        ):
            tokens = tokens[:-1] + [italy_tail]
            cleaned = ' '.join(tokens)

    return clean_text(cleaned)

def _waybill_trim_item_name(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None

    matches = list(re.finditer(r'(?<!\d)(\d{8,14})(?!\d)', cleaned))
    if len(matches) >= 2:
        cleaned = clean_text(cleaned[:matches[1].start()])

    return _waybill_normalize_country_tail(cleaned)


def _waybill_is_total_like_item_row(texts):
    vals = [clean_text(t) for t in texts]
    first = vals[0] or ''
    if not first or len(first) > 16:
        return False
    if re.search(r'\d{8,14}', first):
        return False

    numeric_like = 0
    for t in vals[2:8]:
        if t and re.search(r'\d', t):
            numeric_like += 1

    return numeric_like >= 4

def enrich_waybill_result(result, footer_text, footer_lines=None):
    if not isinstance(result, dict):
        return result
    approvals = result.get("approvals", {})
    footer = result.get("footer", {})
    footer_line_texts = _waybill_footer_line_texts(footer_lines)
    approval_modes = {
        "released_by": "released_by",
        "handed_by": "handed_by",
        "accepted_for_delivery": "accepted_for_delivery",
        "received_by": "received_by",
        "documents_transferred": "documents",
    }

    if footer_line_texts:
        approvals["released_by"] = approvals.get("released_by") or _waybill_collect_footer_phrase(
            footer_line_texts,
            r'Отпуск разрешил\b',
            stop_patterns=(r'Сдал грузоотправитель\b', r'Товар к (?:доставке|перевозке) принял\b'),
            mode=approval_modes["released_by"],
        )
        approvals["handed_by"] = approvals.get("handed_by") or _waybill_collect_footer_phrase(
            footer_line_texts,
            r'Сдал грузоотправитель\b',
            stop_patterns=(r'Товар к (?:доставке|перевозке) принял\b', r'Принял грузополучатель\b'),
            mode=approval_modes["handed_by"],
        )
        approvals["accepted_for_delivery"] = approvals.get("accepted_for_delivery") or _waybill_collect_footer_phrase(
            footer_line_texts,
            r'Товар к (?:доставке|перевозке) принял\b',
            stop_patterns=(r'Принял грузополучатель\b', r'С товаром переданы документы\b'),
            mode=approval_modes["accepted_for_delivery"],
        )
        approvals["received_by"] = approvals.get("received_by") or _waybill_collect_footer_phrase(
            footer_line_texts,
            r'Принял грузополучатель\b',
            stop_patterns=(r'С товаром переданы документы\b', r'Внимание!'),
            mode=approval_modes["received_by"],
        )
        approvals["documents_transferred"] = approvals.get("documents_transferred") or _waybill_collect_footer_phrase(
            footer_line_texts,
            r'С товаром переданы документы\b',
            stop_patterns=(r'РУП\b', r'УП\b', r'Внимание!'),
            mode=approval_modes["documents_transferred"],
        )

        if not footer.get("warning"):
            footer["warning"] = next(
                (line for line in footer_line_texts if re.match(r'^\s*Внимание!', line, flags=re.I)),
                None,
            )

    if footer_text:
        patterns = {
            "released_by": r'((?:Отпуск разрешил\s+)?(?:Специалист по работе с клиентами|Директор).*?)(?=\s+Сдал грузоотправитель\b|\s+Товар к (?:доставке|перевозке) принял\b|\s+\(долж|\s*$)',
            "handed_by": r'(Сдал грузоотправитель.*?)(?=\s+Товар к (?:доставке|перевозке) принял\b|\s+\(долж|\s*$)',
            "accepted_for_delivery": r'(Товар к (?:доставке|перевозке) принял[.:\-]?\s*.*?)(?=\s+по доверенности\b|\s+Принял грузополучатель\b|\s+С товаром (?:переданы|нервданы)\s+документы\b|\s+\(долж|\s*$)',
            "received_by": r'(Принял грузополучатель.*?)(?=\s+С товаром (?:переданы|нервданы)\s+документы\b|\s+Внимание!\b|\s+(?:РУП|УП|Издательство)\b|\s+\(долж|\s*$)',
            "documents_transferred": r'(С товаром (?:переданы|нервданы)\s+документы.*?)(?=\s+Внимание!\b|\s+(?:РУП|УП|Издательство)\b|\s*$)',
        }
        for key, pat in patterns.items():
            if not approvals.get(key):
                m = re.search(pat, footer_text, flags=re.I)
                if m:
                    approvals[key] = _waybill_cleanup_footer_phrase(m.group(1), mode=approval_modes.get(key))
        if not footer.get("warning"):
            m = re.search(r'(Внимание![^\n]*)', footer_text, flags=re.I)
            if m:
                footer["warning"] = clean_text(m.group(1))
    result["approvals"] = approvals
    result["footer"] = footer
    return result
