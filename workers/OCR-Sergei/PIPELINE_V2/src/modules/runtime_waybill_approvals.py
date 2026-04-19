from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_money_words import (
    _format_money_words_ru,
    _money_words_need_rebuild,
    _trim_money_words_ocr_noise,
)
from src.modules.runtime_text_quality import (
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _is_review_field_marker,
    _review_marker_or_none,
)


def normalize_waybill_document_number(value: Any) -> str | None:
    cleaned = _clean_inline_text(value)
    if not cleaned:
        return None
    digits = re.sub(r"\D+", "", cleaned)
    if len(digits) < 6 or len(digits) > 8:
        return None
    significant = digits.lstrip("0")
    if not significant:
        return None
    if len(digits) != 7 and len(significant) < 5:
        return None
    return digits


def normalize_waybill_document_number_or_review(value: Any) -> str | None:
    if _is_review_field_marker(value):
        return REVIEW_FIELD_MARKER
    normalized = normalize_waybill_document_number(value)
    if normalized:
        return normalized
    return _review_marker_or_none(value)


def sanitize_money_words_or_review(raw_value: Any, amount: Any) -> str | None:
    if _is_review_field_marker(raw_value):
        return REVIEW_FIELD_MARKER
    cleaned = _trim_money_words_ocr_noise(raw_value)
    if not cleaned:
        rebuilt = _format_money_words_ru(amount)
        if rebuilt:
            return rebuilt
        return _review_marker_or_none(raw_value)
    if _money_words_need_rebuild(cleaned, amount):
        rebuilt = _format_money_words_ru(amount)
        if rebuilt:
            return rebuilt
        return _review_marker_or_none(raw_value)
    return cleaned


def _looks_like_symbolic_ocr_noise(text: str | None) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    if re.fullmatch(r"[\W_\d]+", cleaned):
        return True
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", cleaned)
    digits = re.findall(r"\d", cleaned)
    return not letters and bool(digits)


def _is_likely_person_role_text(text: str | None) -> bool:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return False
    if len(cleaned) > 90:
        return False
    if re.search(
        r"\b(пломб|погрузоч|разгрузоч|услуг|гознака|издательств|уп\b|руп\b|внимание)\b",
        cleaned,
        flags=re.I,
    ):
        return False
    if re.search(r"[A-Za-z]{4,}", cleaned):
        return False
    if re.search(r"[?\ufffd]", cleaned):
        return False
    has_name = bool(re.search(r"[А-ЯЁ][а-яё-]+\s+[А-ЯЁ]\.[А-ЯЁ]\.", cleaned))
    has_role = bool(
        re.search(
            r"\b(директор|кладовщик|заведующ|агент|специалист|водитель|экспедитор|менеджер|грузоотправител|грузополучател)\w*\b",
            cleaned,
            flags=re.I,
        )
    )
    return has_name or has_role


def _extract_best_person_role_tail(text: str | None) -> str | None:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None
    candidates: list[str] = []
    for pattern in [
        r"Отпуск\s+разре(?:ш|щ)ил\s+(.+)$",
        r"Сдал\s+грузоотправител\w*\s+(.+)$",
        r"Принял\s+грузополучател\w*\s+(.+)$",
    ]:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            candidates.append(_clean_inline_text(match.group(1)) or "")
    fio_like = re.findall(
        r"(?:[А-ЯЁа-яё\"«»().-]+\s+){0,5}[А-ЯЁ][а-яё-]+\s+[А-ЯЁ]\.[А-ЯЁ]\.?",
        cleaned,
        flags=re.I,
    )
    candidates.extend(_clean_inline_text(candidate) or "" for candidate in fio_like)
    candidates = [candidate for candidate in candidates if _is_likely_person_role_text(candidate)]
    if not candidates:
        return None
    return max(candidates, key=len)


def sanitize_waybill_approval_text(text: str | None, *, field_name: str) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    released_prefix = "отпуск разрешил"
    power_of_attorney_phrase = "по доверенности"
    cleaned = re.sub(r"[•▪●○◆■]+", " ", cleaned)
    cleaned = re.sub(r"[\u0600-\u06FF]+", " ", cleaned)
    cleaned = re.sub(
        r"\(\s*должность\s*,?\s*фамилия\s*,?\s*инициалы\s*,?\s*подпись.*$",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\b№\s*пломб\w*.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bпломб\w*.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bпо\s+доверенности\b.*$", "", cleaned, flags=re.I)
    lowered = cleaned.casefold()
    power_of_attorney_pos = lowered.find(power_of_attorney_phrase)
    if power_of_attorney_pos >= 0:
        cleaned = cleaned[:power_of_attorney_pos]
    cleaned = re.sub(r"[.]{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-.")
    cleaned = re.sub(r"\s*№\s*$", "", cleaned).strip(" ,;:-.")
    if field_name == "released_by":
        extracted = _extract_best_person_role_tail(cleaned)
        if extracted:
            cleaned = extracted
        lowered = cleaned.casefold()
        if lowered.startswith(released_prefix):
            cleaned = cleaned[len(released_prefix) :].strip(" ,;:-.")
    elif field_name == "accepted_for_delivery":
        cleaned = re.sub(r"[.]{2,}$", "", cleaned).strip(" ,;:-.")
    if _looks_like_symbolic_ocr_noise(cleaned):
        return None
    if re.search(r"\b(пломб|погрузоч|разгрузоч|услуг|гознака|издательств)\b", cleaned, flags=re.I):
        return None
    if re.findall(r"[A-Za-z]{3,}", cleaned):
        return None
    if field_name in {"received_by", "handed_by", "documents_transferred"} and len(cleaned) <= 2:
        return None
    if field_name in {"released_by", "handed_by", "received_by"} and not _is_likely_person_role_text(cleaned):
        return None
    return cleaned or None


def sanitize_waybill_approval_or_review(raw_value: Any, *, field_name: str) -> str | None:
    if _is_review_field_marker(raw_value):
        return REVIEW_FIELD_MARKER
    sanitized = sanitize_waybill_approval_text(raw_value, field_name=field_name)
    if sanitized:
        return sanitized
    return _review_marker_or_none(raw_value)
