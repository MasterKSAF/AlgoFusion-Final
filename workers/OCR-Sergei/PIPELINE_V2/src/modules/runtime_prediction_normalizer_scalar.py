"""Scalar normalizers for prediction normalization."""

import re

from src.modules.runtime_prediction_normalizer_base import clean_spaces, clean_text, is_nan_like, is_review_field_marker
from src.modules.runtime_prediction_normalizer_config import CYR_TO_LAT_MAP, MONTHS, REVIEW_FIELD_MARKER


def normalize_bool(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"true", "1", "да", "yes"}:
            return True
        if s in {"false", "0", "нет", "no"}:
            return False
    return value

def normalize_number(value, force_int=False):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if force_int:
            return int(round(float(value)))
        val = round(float(value), 2)
        return int(val) if float(val).is_integer() else val

    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP)
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)

    if not s:
        return None

    try:
        num = float(s)
        if force_int:
            return int(round(num))
        num = round(num, 2)
        return int(num) if num.is_integer() else num
    except:
        return value

def normalize_percent(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        num = float(value)
        return f"{int(num) if num.is_integer() else round(num, 2)}%"

    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP)
    s = s.replace("％", "%")
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")

    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    if not m:
        return clean_text(value)

    num = float(m.group(1))
    return f"{int(num) if num.is_integer() else round(num, 2)}%"

def normalize_date(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None
    if not isinstance(value, str):
        return value

    s = clean_spaces(value)
    low = s.lower()

    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{2}:\d{2}))?", low)
    if m:
        dd, mm, yyyy, hm = m.groups()
        out = f"{int(dd):02d}.{int(mm):02d}.{yyyy}"
        if hm:
            out += f" {hm}"
        return out

    m = re.fullmatch(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})(?:\s*(г\.?))?", low)
    if m:
        dd, mon, yyyy, suffix = m.groups()
        if mon in MONTHS:
            out = f"{int(dd)} {mon} {yyyy}"
            if suffix:
                out += " г."
            return out

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", low)
    if m:
        yyyy, mm, dd = m.groups()
        return f"{yyyy}-{mm}-{dd}"

    return s

def normalize_account(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP).upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("О", "0").replace("O", "0")
    s = s.replace("І", "1").replace("I", "1").replace("L", "1")
    return s or None

def normalize_code_text(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    s = s.translate(CYR_TO_LAT_MAP).upper()
    s = re.sub(r"\s+", "", s)
    return s or None

def normalize_phone(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None
    s = clean_spaces(value)
    digits = re.sub(r"[^\d]", "", s)
    if digits.startswith("375") and len(digits) == 12:
        return f"+{digits}"
    return s or None

def normalize_email(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None
    s = clean_spaces(value).lower()
    return s or None

def safe_float(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return 0.0
    try:
        return float(s)
    except:
        return 0.0
