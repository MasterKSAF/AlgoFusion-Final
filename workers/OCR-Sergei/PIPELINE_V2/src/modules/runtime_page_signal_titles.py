from __future__ import annotations

import re


def has_invoice_header_like(top_text: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", str(top_text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return bool(
        re.search(r"\bсч[её]т\s*(?:№|N|No|#)\s*[A-Za-zА-Яа-я0-9\-/]+", text, flags=re.I)
        or re.search(r"\bсч[её]т\b.{0,30}\bот\b.{0,20}[0-3]?\d[./][01]?\d[./]20\d{2}", text, flags=re.I)
        or (
            re.search(r"\bпродавец\s*:", text, flags=re.I)
            and re.search(r"\bпокупател(?:ь|я)\s*:", text, flags=re.I)
        )
    )


def detect_waybill_document_type_text(top_text: str) -> str | None:
    text = re.sub(r"<[^>]+>", " ", str(top_text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if re.search(r"товарно[-\s]*транспортн\w*\s+накладн", text, flags=re.I):
        return "ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ"
    if re.search(r"товарн\w*\s+накладн", text, flags=re.I):
        return "ТОВАРНАЯ НАКЛАДНАЯ"
    return None
