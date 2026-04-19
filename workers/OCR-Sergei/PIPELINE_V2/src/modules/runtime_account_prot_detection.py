from __future__ import annotations

import re

from src.modules.runtime_text_quality import _clean_inline_text


def count_account_prot_pattern_hits(text: str, patterns: list[str]) -> int:
    cleaned = _clean_inline_text(text) or ""
    return sum(1 for pattern in patterns if re.search(pattern, cleaned, flags=re.I))


def looks_like_account_prot_table_header(text: str) -> bool:
    patterns = [
        r"предмет\s+счет",
        r"ед\.?\s*изм",
        r"колич",
        r"свободн",
        r"отпускн",
        r"ставк[аи]",
        r"ндс",
        r"сумма",
    ]
    return count_account_prot_pattern_hits(text, patterns) >= 3
