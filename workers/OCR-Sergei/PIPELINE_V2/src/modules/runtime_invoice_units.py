from __future__ import annotations

import re
from typing import Any

from src.modules.runtime_text_quality import _clean_inline_text


INV_UNIT_PCS = "\u0448\u0442"
INV_UNIT_KG = "\u043a\u0433"
INV_UNIT_ML = "\u043c\u043b"
INV_UNIT_L = "\u043b"
INV_UNIT_PACK = "\u0443\u043f"
VALID_INVOICE_UNITS = frozenset({INV_UNIT_PCS, INV_UNIT_KG, INV_UNIT_ML, INV_UNIT_L, INV_UNIT_PACK})


def normalize_invoice_unit_v2(text: Any) -> str | None:
    unit = _clean_inline_text(text)
    if not unit:
        return None
    unit_lc = (
        unit.lower()
        .replace(".", "")
        .replace(" ", "")
        .replace("\u0458", "")
        .replace("iuit", INV_UNIT_PCS)
        .replace("juit", INV_UNIT_PCS)
        .replace("wr", INV_UNIT_PCS)
        .replace("w", INV_UNIT_PCS)
    )
    collapsed = re.sub(r"[\s._|/\\-]+", "", unit_lc)
    if INV_UNIT_PCS in collapsed:
        return INV_UNIT_PCS
    if INV_UNIT_KG in collapsed:
        return INV_UNIT_KG
    if INV_UNIT_ML in collapsed:
        return INV_UNIT_ML
    if collapsed in {INV_UNIT_L, "ltr", "lt"}:
        return INV_UNIT_L
    if collapsed in {
        INV_UNIT_PACK,
        "\u0443\u043f\u0430\u043a",
        "\u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430",
        "ynak",
        "ynak.",
        "unak",
        "upak",
    }:
        return INV_UNIT_PACK
    if re.fullmatch(r"[a-z]{2,4}", collapsed):
        return INV_UNIT_PCS
    if len(collapsed) <= 4 and collapsed and not re.search(r"\d", collapsed):
        return INV_UNIT_PCS
    return unit


def looks_like_invoice_unit_cell(text: Any) -> bool:
    return normalize_invoice_unit_v2(text) in VALID_INVOICE_UNITS
