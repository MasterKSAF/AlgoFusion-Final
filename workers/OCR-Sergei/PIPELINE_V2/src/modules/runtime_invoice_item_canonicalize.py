from __future__ import annotations

import copy
from typing import Any

from src.modules.runtime_invoice_articles import (
    clean_invoice_description_value,
    extract_invoice_article_candidate,
    normalize_invoice_article_value,
)
from src.modules.runtime_invoice_units import normalize_invoice_unit_v2
from src.modules.runtime_text_quality import _clean_inline_text


def canonicalize_invoice_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        item = copy.deepcopy(row)
        article = normalize_invoice_article_value(item.get("article"))
        description = clean_invoice_description_value(item.get("description"), article=article)
        if article is None and description:
            article = extract_invoice_article_candidate(description, line_number=item.get("line_number"))
            if article:
                stripped = clean_invoice_description_value(description, article=article)
                if stripped:
                    description = stripped
        if article:
            item["article"] = article
        if description:
            item["description"] = description
        unit = normalize_invoice_unit_v2(item.get("unit"))
        if unit:
            item["unit"] = unit
        rate = _clean_inline_text(item.get("vat_rate"))
        if rate:
            item["vat_rate"] = rate.replace(" ", "")
        out.append(item)
    return out
