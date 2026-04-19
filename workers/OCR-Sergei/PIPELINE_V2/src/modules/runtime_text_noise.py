from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_text_common import (
    BAD_SYMBOL_RE,
    REVIEW_FIELD_MARKER,
    _clean_inline_text,
    _collapse_repeated_punctuation,
    _is_review_field_marker,
)


_EDGE_NOISE_CHAR_RE = re.compile(r"[\u0370-\u03FF\u0590-\u05FF\u0600-\u06FF\u0E00-\u0E7F\u20A0-\u20CF\u2190-\u21FF\u2200-\u22FF]")

_LATIN_NOISE_ALLOWLIST = {
    "AQUA",
    "ALPHA",
    "AMBER",
    "ANTI",
    "ANTARCTICA",
    "BAR",
    "BARBER",
    "BLACK",
    "BLOND",
    "BLONDE",
    "CLAY",
    "CLASSIC",
    "COMPLEX",
    "COUTURE",
    "CREAM",
    "CUREX",
    "DAR",
    "DE",
    "DELUXE",
    "DYE",
    "ESTEL",
    "FADEBRUSH",
    "GEL",
    "GOLD",
    "GENWOOD",
    "HAIR",
    "HAUTE",
    "HOMME",
    "KERATIN",
    "LEADER",
    "LEMON",
    "LUXURY",
    "LUXE",
    "MARINE",
    "MASK",
    "MATTE",
    "ML",
    "NISHMAN",
    "PRO",
    "PROFESSIONAL",
    "RU",
    "SENSATION",
    "SERUM",
    "SHAVING",
    "SHAMPOO",
    "SIZE",
    "SPACE",
    "SPRAY",
    "STORM",
    "THERAPY",
    "TOP",
    "VOLUTE",
    "VOLCANO",
    "YELLOW",
}

# Use explicit code points so the regex stays stable even if a Windows editor
# opens the file with the wrong encoding.
_NON_RUSSIAN_CYRILLIC_RE = re.compile(
    r"[\u0406\u0456\u0407\u0457\u0404\u0454\u0490\u0491\u0408\u0458\u040A\u045A\u0409\u0459\u040B\u045B\u040C\u045C\u0402\u0452\u0405\u0455\u040F\u045F]"
)


def _is_edge_noise_token(token: str) -> bool:
    stripped = token.strip(" \t\r\n.,;:()[]{}<>|/\\'\"`~_-")
    if not stripped or len(stripped) > 2:
        return False
    if re.search(r"[A-Za-z\u0400-\u04FF0-9]", stripped):
        return False
    return bool(BAD_SYMBOL_RE.search(stripped) or _EDGE_NOISE_CHAR_RE.search(stripped))


def _trim_edge_noise_tokens(text: str | None) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    tokens = cleaned.split(" ")
    while tokens and _is_edge_noise_token(tokens[0]):
        tokens.pop(0)
    while tokens and _is_edge_noise_token(tokens[-1]):
        tokens.pop()
    return _clean_inline_text(" ".join(tokens))


def _has_nonstandard_text_noise(text: str) -> bool:
    if BAD_SYMBOL_RE.search(text):
        return True
    if re.search(r"[?\ufffd]", text):
        return True
    if re.search(r"[\u0370-\u03FF\u0590-\u05FF\u0600-\u06FF\u0E00-\u0E7F\u20A0-\u20CF\u2190-\u21FF\u2200-\u22FF]", text):
        return True
    return False


def _unknown_latin_words(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z]{3,}", text)
    return [word for word in words if word.upper() not in _LATIN_NOISE_ALLOWLIST]


def _mixed_item_tokens(text: str) -> list[str]:
    mixed_tokens: list[str] = []
    for token in re.split(r"[\s,;:()\"/\\]+", text):
        cleaned = token.strip(".,!?%\u2116-_|")
        if not cleaned:
            continue
        has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", cleaned))
        has_latin = bool(re.search(r"[A-Za-z]", cleaned))
        if not (has_cyrillic and has_latin):
            continue
        upper = cleaned.upper()
        if re.fullmatch(r"[A-Z]{2,}\.[\u0400-\u04FFA-Z-]+", upper):
            continue
        if re.fullmatch(r"[A-Z]{2,}-[\u0400-\u04FF-]+", cleaned):
            continue
        if re.search(r"\bRU(?:\.\d+)+", upper):
            continue
        if "SENSATION" in upper or "ALPHA" in upper:
            continue
        mixed_tokens.append(cleaned)
    return mixed_tokens


def _item_text_has_unreliable_ocr(text: str) -> bool:
    if _has_nonstandard_text_noise(text):
        return True
    unknown_latin = _unknown_latin_words(text)
    has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", text))
    has_repeated_punct = bool(re.search(r"\.{2,}|,{2,}|;{2,}|,\s*\.|\.\s*,", text))
    if has_cyrillic and has_repeated_punct and len(unknown_latin) >= 2:
        return True
    mixed_tokens = _mixed_item_tokens(text)
    has_foreign_cyrillic = bool(_NON_RUSSIAN_CYRILLIC_RE.search(text))
    if has_foreign_cyrillic and len(unknown_latin) >= 2:
        return True
    if has_foreign_cyrillic and len(mixed_tokens) >= 2:
        return True
    if len(mixed_tokens) >= 3 and len(unknown_latin) >= 1:
        return True
    return False


def _invoice_description_has_unreliable_ocr(text: str) -> bool:
    return _has_nonstandard_text_noise(text)


def _strict_text_has_unreliable_ocr(text: str) -> bool:
    if _has_nonstandard_text_noise(text):
        return True
    unknown_latin = _unknown_latin_words(text)
    has_cyrillic = bool(re.search(r"[\u0400-\u04FF]", text))
    has_repeated_punct = bool(re.search(r"\.{3,}|,{2,}|;{2,}", text))
    if has_cyrillic and len(unknown_latin) >= 2:
        return True
    if has_repeated_punct and len(unknown_latin) >= 1:
        return True
    return False


def _sanitize_final_text_or_review(
    raw_value: Any,
    *,
    item_text: bool = False,
    invoice_description: bool = False,
    strict_text: bool = False,
) -> str | None:
    if _is_review_field_marker(raw_value):
        return REVIEW_FIELD_MARKER
    cleaned = _trim_edge_noise_tokens(_clean_inline_text(raw_value))
    if not cleaned:
        return None
    if invoice_description and _invoice_description_has_unreliable_ocr(cleaned):
        return REVIEW_FIELD_MARKER
    if item_text and _item_text_has_unreliable_ocr(cleaned):
        return REVIEW_FIELD_MARKER
    if strict_text and _strict_text_has_unreliable_ocr(cleaned):
        return REVIEW_FIELD_MARKER
    return _collapse_repeated_punctuation(cleaned)
