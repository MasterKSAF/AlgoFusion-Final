from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import clean_text


def _account_prot_extract_total_in_words(footer_text):
    text = clean_text(footer_text)
    if not text:
        return None

    text = re.sub(r'\b[ВVB][сc][еe][ггg][оo]\s*:', 'Всего:', text, flags=re.I)

    patterns = [
        r'Всего:\s*([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
        r'на сумму\s*([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
        r'Сумма прописью[:\s]*([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
        r'([А-ЯЁа-яё][А-ЯЁа-яё\s-]+белорусских рублей\s+\d{1,2}\s+копе[её]к)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.I)
        if matches:
            return clean_text(matches[-1])

    return None

def _account_prot_extract_notes(footer_text):
    text = clean_text(footer_text)
    if not text:
        return None

    a_match = re.search(r'а\)\s*(.+?)(?=\s*б\)|\s*2\.)', text, flags=re.I)
    b_match = re.search(r'б\)\s*(.+?)(?=\s*2\.)', text, flags=re.I)
    step2_match = re.search(
        r'2\.\s*(.+?)(?=\s*(?:Поставщик|Покупатель|МП)\b|$)',
        text,
        flags=re.I,
    )

    if a_match or b_match or step2_match:
        lines = ["При получении товара необходимо:"]
        if re.search(r'1\.\s*Иметь при себе', text, flags=re.I):
            lines.append("1. Иметь при себе")
        else:
            lines.append("1. Иметь при себе")
        if a_match:
            lines.append(f"а) {clean_text(a_match.group(1))}")
        if b_match:
            lines.append(f"б) {clean_text(b_match.group(1))}")
        if step2_match:
            lines.append(f"2. {clean_text(step2_match.group(1))}")
        return "\n".join(line for line in lines if line)

    match = re.search(
        r'(При получении товара необходимо:.*?)(?=\s*(?:Поставщик|Покупатель|МП)\b|$)',
        text,
        flags=re.I,
    )
    return clean_text(match.group(1)) if match else None
