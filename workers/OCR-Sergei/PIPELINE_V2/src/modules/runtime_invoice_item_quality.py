from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_invoice_articles import normalize_invoice_article_value
from src.modules.runtime_invoice_cells import looks_like_money_text
from src.modules.runtime_invoice_units import normalize_invoice_unit_v2
from src.modules.runtime_text_quality import _clean_inline_text


def invoice_item_suspicious(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return True
    line_number = item.get("line_number")
    article = normalize_invoice_article_value(item.get("article")) or ""
    unit = _clean_inline_text(item.get("unit")) or ""
    desc = _clean_inline_text(item.get("description")) or ""
    rate = _clean_inline_text(item.get("vat_rate")) or ""
    if rate and rate not in {"0%", "10%", "20%"}:
        return True
    if isinstance(line_number, (int, float)):
        line_prefix = str(int(line_number))
        if article.startswith(line_prefix) and len(article) > len(line_prefix):
            next_char = article[len(line_prefix) : len(line_prefix) + 1]
            if re.fullmatch(r"[A-ZА-Я]", next_char, flags=re.I):
                return True
    if unit and normalize_invoice_unit_v2(unit) is None:
        return True
    if unit and (looks_like_money_text(unit) or re.search(r"\d{6,}", unit)):
        return True
    if desc and re.fullmatch(r"\d{8,14}", desc):
        return True
    if desc and re.search(r"\b\d{1,3}\s+[A-ZА-Я0-9]{1,8}\s*/\s*[A-ZА-Я0-9./-]{1,16}\b", desc, flags=re.I):
        return True
    return False
