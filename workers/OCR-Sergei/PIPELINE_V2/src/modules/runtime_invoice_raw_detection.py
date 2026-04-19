from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_text_quality import _clean_inline_text


def count_pattern_hits(text: Any, patterns: list[str]) -> int:
    source = _clean_inline_text(text) or ""
    return sum(1 for pattern in patterns if re.search(pattern, source, flags=re.I))


def normalize_invoice_unit(text: Any) -> str | None:
    unit = _clean_inline_text(text)
    if not unit:
        return None
    unit_lc = unit.lower().replace(".", "").replace(" ", "")
    if "шт" in unit_lc:
        return "шт"
    if "кг" in unit_lc:
        return "кг"
    if "мл" in unit_lc:
        return "мл"
    if unit_lc in {"л", "ltr", "lt"}:
        return "л"
    if re.fullmatch(r"[a-z]{2,4}", unit_lc):
        return "шт"
    return unit


def looks_like_invoice_table_header(text: str) -> bool:
    patterns = [
        r"\bартикул\b",
        r"\bтовар\b",
        r"\bштрих\b",
        r"\bцена\b",
        r"\bсумма\b",
        r"\bндс\b",
        r"\bкол(?:-во|ичество)?\b",
        r"\bед\.?\b",
    ]
    return count_pattern_hits(text, patterns) >= 3


def looks_like_invoice_index_row(texts: list[str]) -> bool:
    nonempty = [_clean_inline_text(text) for text in texts if _clean_inline_text(text)]
    if len(nonempty) < 8:
        return False
    if any(re.search(r"(итого|всего|внимание)", text, flags=re.I) for text in nonempty):
        return False
    short_ratio = sum(1 for text in nonempty if len(text) <= 4) / max(1, len(nonempty))
    long_word_count = sum(1 for text in nonempty if re.search(r"[A-Za-zА-Яа-яЁё]{5,}", text))
    return short_ratio >= 0.75 and long_word_count <= 1
