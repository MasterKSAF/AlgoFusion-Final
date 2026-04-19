"""Text normalizers for prediction normalization."""

import re

from src.modules.runtime_prediction_normalizer_base import clean_spaces, clean_text, is_nan_like, is_review_field_marker
from src.modules.runtime_prediction_normalizer_config import REVIEW_FIELD_MARKER, VISUAL_QUOTES_MAP


def normalize_generic_text(value):
    if is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    if is_nan_like(value):
        return None

    s = clean_spaces(value)
    s = s.translate(VISUAL_QUOTES_MAP)
    s = re.sub(r"<[^>]+>", " ", s)

    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")

    return s or None

def normalize_free_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"\bДата документа:?\s*$", "", s, flags=re.I).strip(" ,;:")
    return s or None

def normalize_address_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"^\s*,\s*", "", s)

    # "6a" -> "6а" в адресном контексте
    s = re.sub(r"(\d)\s*([aA])\b", r"\1а", s)

    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None

def normalize_bank_name_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"^\s*в банке\s+", "", s, flags=re.I)
    s = re.sub(r"\b(?:БИК|BIC|Код банка)\b.*$", "", s, flags=re.I)
    s = re.sub(r"\b[A-Z]{6}[A-Z0-9]{2}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None

def normalize_party_name_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(
        r"^\s*(Организация|Поставщик|Покупатель|Плательщик|Бенефициар|Грузоотправитель|Грузополучатель)\s*:?\s*",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"\bограниченно\s+й\b", "ограниченной", s, flags=re.I)
    s = re.sub(r"\bо\s+тветственностью\b", "ответственностью", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None

def normalize_unit_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    low = s.lower().replace(".", "").strip()
    compact = re.sub(r"\s+", "", low)
    if compact in {"шт", "шτ", "шп", "sp", "pc", "pcs", "iuit", "juit", "wr", "w"}:
        return "шт"
    if compact in {"уп", "упак", "упаковка"}:
        return "уп"
    if compact in {"кг", "мл", "л"}:
        return compact
    return compact or None

def normalize_product_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    # "HOMME. 200 мл" -> "HOMME, 200 мл"
    s = re.sub(
        r"([A-Za-zА-Яа-яЁё])\.\s+(?=\d+\s*(?:мл|г|кг|л|см|мм|шт|м|мкм)\b)",
        r"\1, ",
        s,
    )

    # "1000 мл. 460645..." -> "1000 мл, 460645..."
    s = re.sub(
        r"(\d+\s*(?:мл|г|кг|л|см|мм|шт|м|мкм))\.\s+(?=\d{8,14}\b)",
        r"\1, ",
        s,
    )

    s = re.sub(
        r"\.\s+(?=(?:\d+\s*(?:мл|г|кг|л|см|мм|шт|м|мкм)\b|\d{8,14}\b))",
        ", ",
        s,
    )

    s = re.sub(r"\s*,\s*", ", ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None

def normalize_money_words_text(value):
    s = normalize_generic_text(value)
    if not s:
        return None

    s = re.sub(r"\bкопейк\b", "копейки", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*руб\b\.?", " руб.", s, flags=re.I)
    s = re.sub(r"(?<=\d)\s*коп\b\.?", " коп.", s, flags=re.I)

    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    return s or None

def is_total_row(item):
    if not isinstance(item, dict):
        return False
    label = item.get("name") or item.get("description") or ""
    label = normalize_generic_text(label)
    if not label:
        return False
    return label.lower() in {"итого", "итог", "итого:"}
