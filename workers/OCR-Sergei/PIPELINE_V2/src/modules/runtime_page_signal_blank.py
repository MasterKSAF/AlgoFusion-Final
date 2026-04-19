from __future__ import annotations

import re


def is_precomputed_blank_page(full_text: str) -> bool:
    return len(re.sub(r"\s+", "", full_text)) < 25


def is_blank_page_v3(*, full_text: str, has_title: bool, has_footer: bool) -> bool:
    compact_text_len = len(re.sub(r"\s+", "", full_text))
    useful_tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]{2,}", full_text)
    useful_chars = sum(len(token) for token in useful_tokens)
    return (compact_text_len < 25 or (useful_chars < 18 and len(useful_tokens) <= 3)) and not has_title and not has_footer
