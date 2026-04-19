from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import clean_text


def cut_basis(text):
    if not text:
        return None
    stop_words = ["Сумма", "Итого", "Всего", "ВНИМАНИЕ"]
    pos = len(text)
    for w in stop_words:
        i = text.find(w)
        if i != -1:
            pos = min(pos, i)
    return text[:pos].strip(" ,")

def merge_multiline(text):
    if not text:
        return None
    text = re.sub(r"\s+", " ", str(text))
    return text.strip(" ,")

def clean_invoice_date(text):
    text = clean_text(text)
    if not text:
        return None
    text = re.sub(r"\s+г\.\s*$", "", text, flags=re.I)
    return text

def extract_phone_pretty(s):
    if not s:
        return None
    m = re.search(r'(\+375)\s*\(?(\d{2})\)?\s*(\d{3})[-\s]*(\d{2})[-\s]*(\d{2})', s)
    if not m:
        return None
    return f"{m.group(1)} ({m.group(2)}) {m.group(3)}-{m.group(4)}-{m.group(5)}"

def extract_invoice_note(footer_text):
    if not footer_text:
        return None
    m = re.search(
        r'(ВНИМАНИЕ!!!\s*Счет действителен в течение\s*\d+\s*дн\w*)',
        footer_text,
        flags=re.I
    )
    return clean_text(m.group(1)) if m else None

def clean_invoice_footer_text(footer_text):
    if not footer_text:
        return None
    text = clean_text(footer_text)
    text = re.sub(r'<del>.*?</del>', ' ', text, flags=re.I)
    text = re.sub(r'\bSalara\s+Augus\b', ' ', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_invoice_total_in_words(footer_text):
    if not footer_text:
        return None

    text = clean_invoice_footer_text(footer_text) or footer_text
    text = re.sub(r'ВНИМАНИЕ!!!.*$', ' ', text, flags=re.I)
    text = re.sub(r'\bна сумму\b', ' ', text, flags=re.I)
    text = re.sub(r'\b\d+[.,]\d{2}\s*BYN\b', ' ', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()

    m = re.search(
        r'([А-ЯЁа-яё]+(?:\s+[А-ЯЁа-яё-]+)*\s+рубл[яей]\s+\d{1,2}\s+копе[йе]к)',
        text,
        flags=re.I
    )
    if m:
        val = clean_text(m.group(1))
        val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
        return val

    m = re.search(r'на сумму\s*([^\.]+)', footer_text, flags=re.I)
    if m:
        val = clean_text(m.group(1))
        if val:
            val = re.sub(r'^\d+[.,]\d{2}\s*BYN\s*', '', val, flags=re.I)
            val = re.sub(r'\s*ВНИМАНИЕ!!!.*$', '', val, flags=re.I)
            val = re.sub(r'копейк$', 'копейки', val, flags=re.I)
            return clean_text(val)

    return None

def extract_invoice_signatory(footer_text):
    signatory = {"position": None, "name": None}
    if not footer_text:
        return signatory

    m = re.search(
        r'(Специалист по работе с клиентами|Менеджер|Директор)\s+([А-ЯЁ][а-яё]+(?:\s*[А-ЯЁ]\.[А-ЯЁ]\.))',
        footer_text
    )
    if m:
        signatory["position"] = clean_text(m.group(1))
        signatory["name"] = clean_text(m.group(2))

    return signatory
