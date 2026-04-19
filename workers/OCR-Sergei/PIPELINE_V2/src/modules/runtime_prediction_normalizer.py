from __future__ import annotations

"""Prediction normalization orchestration."""

import re

from src.modules.runtime_prediction_normalizer_helpers import (
    ACCOUNT_KEYS,
    ADDRESS_KEYS,
    BANK_NAME_KEYS,
    BOOL_KEY_HINTS,
    CODE_KEYS,
    DATE_KEY_HINTS,
    FREE_TEXT_KEYS,
    INT_KEY_HINTS,
    MONEY_WORD_KEYS,
    NUMERIC_KEY_HINTS,
    PARTY_BLOCK_KEYS,
    PERCENT_KEY_HINTS,
    CYR_TO_LAT_MAP,
    REVIEW_FIELD_MARKER,
    clean_spaces,
    clean_text,
    is_nan_like,
    is_party_name_field,
    is_product_text_field,
    is_review_field_marker,
    is_total_row,
    normalize_account,
    normalize_address_text,
    normalize_bank_name_text,
    normalize_bool,
    normalize_code_text,
    normalize_date,
    normalize_email,
    normalize_free_text,
    normalize_generic_text,
    normalize_money_words_text,
    normalize_number,
    normalize_party_name_text,
    normalize_percent,
    normalize_phone,
    normalize_product_text,
    normalize_unit_text,
    path_has,
    path_leaf,
    safe_float,
)

def cleanup_items_and_totals(obj):
    if isinstance(obj, dict):
        cleaned = {k: cleanup_items_and_totals(v) for k, v in obj.items()}

        if isinstance(cleaned.get("items"), list):
            cleaned["items"] = [x for x in cleaned["items"] if not is_total_row(x)]

        return cleaned

    if isinstance(obj, list):
        return [cleanup_items_and_totals(x) for x in obj]

    return obj


def normalize_by_path(path, value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None

    leaf = path_leaf(path)

    if leaf in BOOL_KEY_HINTS:
        return normalize_bool(value)

    if leaf in DATE_KEY_HINTS:
        return normalize_date(value)

    if leaf in PERCENT_KEY_HINTS:
        return normalize_percent(value)

    if leaf in INT_KEY_HINTS:
        return normalize_number(value, force_int=True)

    if leaf in NUMERIC_KEY_HINTS:
        return normalize_number(value, force_int=False)

    if leaf in ACCOUNT_KEYS:
        return normalize_account(value)

    if leaf in CODE_KEYS:
        return normalize_code_text(value)

    if leaf == "phone":
        return normalize_phone(value)

    if leaf == "email":
        return normalize_email(value)

    if leaf == "unit":
        return normalize_unit_text(value)

    if leaf in MONEY_WORD_KEYS:
        return normalize_money_words_text(value)

    if leaf in ADDRESS_KEYS:
        return normalize_address_text(value)

    if leaf in BANK_NAME_KEYS:
        return normalize_bank_name_text(value)

    if is_product_text_field(path):
        return normalize_product_text(value)

    if is_party_name_field(path):
        return normalize_party_name_text(value)

    if leaf in FREE_TEXT_KEYS:
        return normalize_free_text(value)

    if isinstance(value, str):
        s = clean_spaces(value)

        # Осторожный fallback: если строка действительно выглядит как число
        s_num = s.translate(CYR_TO_LAT_MAP)
        s_num = s_num.replace(",", ".")
        s_num = re.sub(r"[^\d.\-%]", "", s_num)

        if s_num:
            try:
                if "%" in s_num:
                    num = float(s_num.replace("%", ""))
                    return f"{int(num) if num.is_integer() else round(num, 2)}%"
                num = float(s_num)
                num = round(num, 2)
                return int(num) if num.is_integer() else num
            except:
                pass

        return normalize_generic_text(s)

    return value

def walk(obj, path=()):
    if isinstance(obj, dict):
        return {k: walk(v, path + (k,)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(x, path + ("[]",)) for x in obj]
    return normalize_by_path(path, obj)

def normalize_pred(pred_raw):
    return cleanup_items_and_totals(walk(pred_raw))
