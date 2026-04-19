from __future__ import annotations

import re

from src.modules.runtime_text_quality import _clean_inline_text


def extract_invoice_signatory_from_text(text: str) -> tuple[str | None, str | None]:
    cleaned = _clean_inline_text(re.sub(r"\s+", " ", str(text or ""))) or ""
    if not cleaned:
        return None, None

    position_patterns = [
        r"Директор",
        r"Руководитель",
        r"Специалист\s+по\s+работе\s+с\s+клиентами",
        r"Менеджер(?:\s+по\s+[А-Яа-яЁё-]+)?",
        r"Бухгалтер",
    ]
    fio_pattern = r"([А-ЯЁ][А-Яа-яЁё-]+\s+[А-ЯЁ]\.[А-ЯЁ]\.?)"

    for position_pattern in position_patterns:
        match = re.search(
            rf"({position_pattern})\s*(?:\||:)?\s*\(?{fio_pattern}\)?",
            cleaned,
            flags=re.I,
        )
        if match:
            return _clean_inline_text(match.group(1)), _clean_inline_text(match.group(2))

    for position_pattern in position_patterns:
        match = re.search(rf"({position_pattern})(?:\s+[А-ЯЁ][^|]{{0,40}})?", cleaned, flags=re.I)
        fio_match = re.search(fio_pattern, cleaned)
        if match and fio_match and fio_match.start() >= match.start():
            return _clean_inline_text(match.group(1)), _clean_inline_text(fio_match.group(1))

    return None, None
