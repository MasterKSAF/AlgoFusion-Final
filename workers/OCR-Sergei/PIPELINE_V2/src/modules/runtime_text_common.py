from __future__ import annotations

import re
from typing import Any


REVIEW_FIELD_MARKER = "\u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043f\u043e\u043b\u0435"

_BAD_SYMBOL_CHARS = (
    "\uFFFD\u017D\u017E\u0160\u0161\u010C\u010D\u0106\u0107\u0141\u0142"
    "\u0110\u0111\u0104\u0105\u0118\u0119\u0172\u0173\u016A\u016B"
    "\u0116\u0117\u0130\u0131\u00D8\u00F8\u00C6\u00E6\u0152\u0153"
    "\u00D0\u00F0\u00DE\u00FE\u2022\u00B7\u00F7\u25AA\u25CF\u25CB"
    "\u25E6\u25A0\u25A1\U0001F42B\U0001F908\u2234"
)
BAD_SYMBOL_RE = re.compile("[" + re.escape(_BAD_SYMBOL_CHARS) + "]")


def _clean_inline_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    return cleaned or None


def _is_review_field_marker(value: Any) -> bool:
    cleaned = _clean_inline_text(value)
    return bool(cleaned and cleaned.lower() == REVIEW_FIELD_MARKER)


def _review_marker_or_none(raw_value: Any) -> str | None:
    return REVIEW_FIELD_MARKER if _clean_inline_text(raw_value) else None


def _collapse_repeated_punctuation(text: str | None) -> str | None:
    cleaned = _clean_inline_text(text)
    if not cleaned:
        return None
    cleaned = re.sub("(\u2116)\\s*\\.{2,}", r"\1 ", cleaned)
    cleaned = re.sub(r",\s*\.{2,}", ",", cleaned)
    cleaned = re.sub(r"\.\s*,", ",", cleaned)
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r",{2,}", ",", cleaned)
    cleaned = re.sub(r";{2,}", ";", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:-")
    return cleaned or None
