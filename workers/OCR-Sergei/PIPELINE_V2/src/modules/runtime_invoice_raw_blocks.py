from __future__ import annotations

import re

from shared.resources.text_lexicon import INVOICE_TOTAL_LINE_PATTERN
from src.modules.runtime_invoice_raw_detection import (
    looks_like_invoice_index_row,
    looks_like_invoice_table_header,
)
from src.modules.runtime_text_quality import _clean_inline_text


def _is_invoice_total_line(text: str) -> bool:
    return bool(re.search(INVOICE_TOTAL_LINE_PATTERN, text, flags=re.I))


def _is_invoice_header_line(text: str) -> bool:
    lowered = text.lower()
    return looks_like_invoice_table_header(text) or (
        "наименование" in lowered and "цена" in lowered and ("ндс" in lowered or "сумма" in lowered)
    )


def _is_invoice_header_garbage_line(text: str) -> bool:
    compact = [part for part in re.split(r"\s*\|\s*|\s{2,}", text) if _clean_inline_text(part)]
    return looks_like_invoice_index_row(compact) or text.strip().lower() in {"men.", "мен."}


def _is_invoice_item_start_line(text: str) -> bool:
    return bool(
        re.match(r"^\s*(?:\d+\s+)?(?=[^\s|]{3,}\b)(?=.*\d)[^\s|]{3,}\b", text)
        or re.match(r"^\s*\d{4,}\s+\S", text)
    )


def collect_invoice_raw_item_blocks(lines: list[str]) -> list[list[str]]:
    if not lines:
        return []

    body_started = False
    blocks: list[list[str]] = []
    current: list[str] = []

    for raw_line in lines:
        line = _clean_inline_text(raw_line)
        if not line:
            continue
        if not body_started:
            if _is_invoice_header_line(line):
                body_started = True
            continue
        if _is_invoice_total_line(line):
            break
        if _is_invoice_header_garbage_line(line):
            continue
        if _is_invoice_item_start_line(line):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)

    if current:
        blocks.append(current)
    return blocks
