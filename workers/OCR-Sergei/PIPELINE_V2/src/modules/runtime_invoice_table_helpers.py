from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    CYR_TO_LAT,
    MONTHS_RU,
    clean_text,
    cleanup_bank_name,
    extract_all_tax_ids,
    extract_bank_account,
    extract_bic,
    extract_company_names,
    extract_kpp,
    extract_tax_id,
    filter_table_rows,
    get_regions,
    group_rows,
    is_index_row,
    load_json,
    looks_like_table_header,
    normalize_account,
    normalize_percent,
    row_texts,
    to_float,
    to_int,
)

# =========================
# Invoice
# =========================

def invoice_is_header_row(texts):
    return looks_like_table_header(texts)


def invoice_is_index_row(texts):
    return is_index_row(texts)


def is_valid_item_row(texts):
    if len(texts) < 10:
        return False

    if invoice_is_header_row(texts):
        return False

    if invoice_is_index_row(texts):
        return False

    joined = " ".join(texts).lower()

    if any(x in joined for x in [
        "итого", "всего наименований", "внимание",
        "специалист", "кисел"
    ]):
        return False

    nonempty = [clean_text(x) for x in texts if clean_text(x)]

    if nonempty and all(re.fullmatch(r"\d{1,2}", x) for x in nonempty):
        return False

    short_numeric = sum(1 for x in nonempty if re.fullmatch(r"\d{1,2}", x or ""))
    if nonempty and short_numeric / len(nonempty) >= 0.7:
        return False

    has_article = bool(texts[1]) if len(texts) > 1 else False
    has_desc = bool(texts[2]) if len(texts) > 2 else False

    if re.fullmatch(r"\d{1,2}", str(texts[1]).strip() if len(texts) > 1 else ""):
        has_article = False
    if re.fullmatch(r"\d{1,2}", str(texts[2]).strip() if len(texts) > 2 else ""):
        has_desc = False

    numeric_fields = sum(
        1 for t in texts[4:12]
        if to_float(t) is not None
    )

    return (has_article or has_desc) and numeric_fields >= 3


def parse_line_number(text, fallback):
    cleaned = clean_text(text)
    if not cleaned:
        return fallback

    compact = re.sub(r'\s+', '', cleaned)
    v = to_int(compact)
    if v is None:
        return fallback

    if fallback is not None:
        if v == fallback:
            return v

        digit_tokens = re.findall(r'\d+', cleaned)
        if len(digit_tokens) >= 2:
            first = to_int(digit_tokens[0])
            joined = to_int(''.join(digit_tokens))

            if joined == fallback:
                return fallback
            if first == fallback and v > fallback + 1:
                return fallback

        if re.search(r'\d\s+\d', cleaned) and v > fallback + 1:
            return fallback

    return v


def normalize_unit(u):
    if not u:
        return None
    u = u.lower().replace(".", "").strip()
    if u in {"шт", "шτ", "யா", "wr", "wt"}:
        return "шт"
    return u


def extract_invoice_numeric_totals(table_rows):
    totals = {
        "total_quantity": None,
        "subtotal_no_disc_incl_vat": None,
        "total_disc_amount": None,
        "subtotal_with_disc_excl_vat": None,
        "vat_amount": None,
        "total_with_disc_incl_vat": None,
        "total_in_words": None,
        "currency": "BYN",
    }

    for row in table_rows:
        texts = row_texts(row)
        joined = " | ".join(texts).lower()

        if "итого" not in joined:
            continue

        texts = texts + [""] * (13 - len(texts))

        totals["total_quantity"] = to_int(texts[4])
        totals["subtotal_no_disc_incl_vat"] = to_float(texts[7])
        totals["total_disc_amount"] = to_float(texts[8])
        totals["subtotal_with_disc_excl_vat"] = to_float(texts[9])
        totals["vat_amount"] = to_float(texts[11])
        totals["total_with_disc_incl_vat"] = to_float(texts[12])
        break

    return totals
