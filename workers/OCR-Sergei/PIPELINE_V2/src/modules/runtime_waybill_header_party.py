from __future__ import annotations

import re
from typing import Any

from shared.resources.text_lexicon import (
    COMPANY_FORMS_PATTERN,
    COMPANY_QUOTED_NAME_PATTERNS,
    WAYBILL_ADDRESS_SCORE_TOKEN_PATTERN,
    WAYBILL_ADDRESS_TOKEN_PATTERN,
    WAYBILL_HEADER_ANCHOR_NOISE_PATTERN,
)
from src.modules.runtime_text_quality import _clean_inline_text


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0 or all(is_missing(item) for item in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(is_missing(item) for item in value.values())
    return False


def looks_like_address_only(text: str) -> bool:
    source = str(text or "")
    cleaned = _clean_inline_text(text) or source
    if not cleaned:
        return False
    if re.search(r'^\?{2,5}\s*["“]', source):
        return False
    if re.search(
        rf"\b(?:{COMPANY_FORMS_PATTERN})\b",
        source,
        flags=re.I,
    ):
        return False
    if re.search(r"\?\.\s+\?{3,}(?:,\s+\?\?\.\s+\?{3,})?", source):
        return True
    return bool(
        re.search(
            WAYBILL_ADDRESS_TOKEN_PATTERN,
            source,
            flags=re.I,
        )
    )


def has_waybill_header_anchor_noise(text: str | None) -> bool:
    source = str(text or "")
    cleaned = _clean_inline_text(text) or source
    if not cleaned:
        return False
    return bool(
        re.search(
            WAYBILL_HEADER_ANCHOR_NOISE_PATTERN,
            source,
            flags=re.I,
        )
    )


def waybill_party_payload_suspicious(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    name = _clean_inline_text(payload.get("name")) or ""
    address = _clean_inline_text(payload.get("address")) or ""
    combined = " ".join(part for part in [name, address] if part).strip()
    if not combined:
        return False
    return has_waybill_header_anchor_noise(combined)


def score_waybill_party_value(text: str) -> int:
    source = str(text or "")
    cleaned = _clean_inline_text(text) or source
    if not cleaned:
        return -10_000
    score = len(cleaned)
    if re.search(r"\b[1-4]-й\s+экз", source, flags=re.I):
        score -= 500
    if re.search(rf"\b(?:{COMPANY_FORMS_PATTERN})\b", source, flags=re.I):
        score += 100
    if re.search(WAYBILL_ADDRESS_SCORE_TOKEN_PATTERN, source, flags=re.I):
        score += 25
    if len(cleaned.split()) < 3:
        score -= 50
    return score


def split_person_value_pair(text: str) -> tuple[str | None, str | None]:
    cleaned = _clean_inline_text(text) or ""
    if not cleaned:
        return None, None
    # Keep the split Unicode-safe and avoid mojibake-sensitive character ranges.
    fio_match = re.search(r"^(.*?\b[^\W\d_]\.[^\W\d_]\.)\s+(.*)$", cleaned, flags=re.UNICODE)
    if fio_match:
        return _clean_inline_text(fio_match.group(1)), _clean_inline_text(fio_match.group(2))
    return _clean_inline_text(cleaned), None


def waybill_party_candidate_confident(name: str | None, address: str | None = None) -> bool:
    source_name = str(name or "")
    clean_name = _clean_inline_text(name) or source_name
    clean_address = _clean_inline_text(address) or str(address or "")
    if not clean_name:
        return False
    if looks_like_address_only(clean_name):
        return False
    if re.search(r"\b(c/c|с/с|р-н|ул\.|дом|пом\.|каб\.)\b", source_name, flags=re.I):
        return False
    if re.search(rf"\b(?:{COMPANY_FORMS_PATTERN})\b", source_name, flags=re.I):
        return True
    if clean_address and len(clean_name.split()) >= 3:
        return True
    return False


def extract_company_name_address(text: str) -> tuple[str | None, str | None]:
    cleaned = str(text or "")
    cleaned = re.sub(r"^\([^)]*\)\s*", "", cleaned)
    cleaned = re.sub(r"\(\s*наим[^)]*\)", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\(\s*адрес[^)]*\)", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;")
    if not cleaned:
        return None, None

    for pattern in COMPANY_QUOTED_NAME_PATTERNS:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            name = _clean_inline_text(match.group(1))
            rest = _clean_inline_text(cleaned[match.end() :].lstrip(" ,;"))
            return name, rest

    if "," in cleaned:
        head, tail = cleaned.split(",", 1)
        return _clean_inline_text(head), _clean_inline_text(tail)
    return cleaned, None
