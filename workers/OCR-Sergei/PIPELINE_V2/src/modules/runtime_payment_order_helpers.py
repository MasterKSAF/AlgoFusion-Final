from __future__ import annotations

import re
from pathlib import Path

from src.modules.runtime_document_parser_common import (
    _extract_bic_candidates,
    _normalize_bic_token,
    choose_best_code_prefixed_text,
    clean_text,
    cleanup_bank_name,
    extract_all_accounts,
    extract_all_bics,
    extract_all_datetimes,
    extract_all_tax_ids,
    extract_bank_account,
    extract_company_names,
    extract_person_name,
    get_regions,
    load_json,
    normalize_leading_code_prefix,
    row_texts,
    to_float,
)
# =========================
# Payment order
# =========================

def build_form_text_map(regions):
    vals = []
    for r in regions:
        if r.get("kind") == "form_roi":
            t = clean_text(r.get("text"))
            if t is not None:
                vals.append(t)
    return vals

def find_first(lines, pattern, flags=re.I):
    rx = re.compile(pattern, flags)
    for line in lines:
        m = rx.search(line)
        if m:
            return m
    return None

def strip_po_markup(text):
    cleaned = clean_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r'<\s*br\s*/?\s*>', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'</?(?:b|u|i|em|strong|span|div|p)[^>]*>', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return clean_text(cleaned)

def normalize_po_bic_candidate(text):
    cleaned = strip_po_markup(text)
    if not cleaned:
        return None
    return _normalize_bic_token(cleaned)

def extract_all_po_bics(text):
    return _extract_bic_candidates(strip_po_markup(text))

def normalize_po_bank_name(text):
    cleaned = strip_po_markup(text)
    if not cleaned:
        return None

    stop_patterns = (
        r'\bСчет\s*№\b',
        r'\bКод\s+банка\b',
        r'\bПодпись\s+исполнителя\s+банка\b',
        r'\bДата\s+поступления\b',
        r'\bДата\s+исполнения\b',
        r'\bШтамп\s+банка\b',
        r'\bНазначение\s+платежа\b',
        r'\b№\s*документа\b',
        r'\bУНП\b',
        r'\bОчередь\b',
    )
    cut_at = len(cleaned)
    for pattern in stop_patterns:
        match = re.search(pattern, cleaned, flags=re.I)
        if match:
            cut_at = min(cut_at, match.start())

    cleaned = clean_text(cleaned[:cut_at])
    if not cleaned:
        return None
    cleaned = cleanup_bank_name(cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return clean_text(cleaned)

def enrich_payment_order_result(result, lines, full):
    doc = next(iter(result.get("payment_order", {}).values()), None)
    if not doc:
        return result
    payer = doc.get("payer", {})
    payee = doc.get("payee", {})
    payment_details = doc.get("payment_details", {})
    execution_details = doc.get("execution_details", {})

    accounts = extract_all_accounts(full)
    tax_ids = extract_all_tax_ids(full)
    bics = extract_all_po_bics(full)
    datetimes = extract_all_datetimes(full)
    company_names = extract_company_names(full)

    if not payer.get("bank_account") and len(accounts) > 0:
        payer["bank_account"] = accounts[0]
    if not payee.get("bank_account") and len(accounts) > 1:
        payee["bank_account"] = accounts[1]
    if not payer.get("tax_id") and len(tax_ids) > 0:
        payer["tax_id"] = tax_ids[0]
    if not payee.get("tax_id") and len(tax_ids) > 1:
        payee["tax_id"] = tax_ids[1]
    if not payer.get("bank_code") and len(bics) > 0:
        payer["bank_code"] = bics[0]
    if not payee.get("bank_code") and len(bics) > 1:
        payee["bank_code"] = bics[1]

    payer_bic_norm = normalize_po_bic_candidate(payer.get("bank_code")) if payer.get("bank_code") else None
    payee_bic_norm = normalize_po_bic_candidate(payee.get("bank_code")) if payee.get("bank_code") else None
    known_bics = set(bics)

    if payer.get("bank_code") and (
        not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}', payer_bic_norm or '')
        or (known_bics and payer_bic_norm not in known_bics)
    ) and len(bics) > 0:
        payer["bank_code"] = bics[0]

    if payee.get("bank_code") and (
        not re.fullmatch(r'[A-Z]{6}[A-Z0-9]{2}', payee_bic_norm or '')
        or (known_bics and payee_bic_norm not in known_bics)
    ) and len(bics) > 1:
        payee["bank_code"] = bics[1]
    if not payer.get("name") and len(company_names) > 0:
        payer["name"] = company_names[0]
    if not payee.get("name") and len(company_names) > 1:
        payee["name"] = company_names[1]
    if payer.get("bank_name"):
        payer["bank_name"] = normalize_po_bank_name(payer.get("bank_name"))
    if payee.get("bank_name"):
        payee["bank_name"] = normalize_po_bank_name(payee.get("bank_name"))

    if not execution_details.get("receipt_date") and len(datetimes) > 0:
        execution_details["receipt_date"] = datetimes[0]
    if not execution_details.get("execution_date") and len(datetimes) > 1:
        execution_details["execution_date"] = datetimes[1]
    if not execution_details.get("status"):
        m = re.search(r'\b(исполнено|принято|обработано)\b', full, flags=re.I)
        if m:
            execution_details["status"] = clean_text(m.group(1))
    suspicious_exec = execution_details.get("executing_bank") and re.search(
        r'Код\s+банка|Назначение\s+платежа|Счет\s*№|УНП|Очередь|Подпись',
        execution_details.get("executing_bank") or '',
        flags=re.I,
    )
    if suspicious_exec:
        execution_details["executing_bank"] = None
    if not execution_details.get("executing_bank"):
        payer_bank = normalize_po_bank_name(payer.get("bank_name"))
        if payer_bank and re.search(r'банк', payer_bank, flags=re.I):
            execution_details["executing_bank"] = payer_bank
        else:
            bank_names = [normalize_po_bank_name(x) for x in company_names if 'банк' in x.lower()]
            bank_names = [x for x in bank_names if x]
            if bank_names:
                execution_details["executing_bank"] = bank_names[-1]

    if not doc.get("payment_order_number"):
        m = re.search(r'№\s*(\d{1,4})', full)
        if m:
            doc["payment_order_number"] = clean_text(m.group(1))
    if not doc.get("payment_order_type"):
        m = re.search(r'\(([^)]+)\)', full)
        if m:
            doc["payment_order_type"] = clean_text(m.group(1))
    if not payment_details.get("payment_priority"):
        m = re.search(r'(?:очеред|приоритет)[^0-9]{0,10}(\d{1,2})', full, flags=re.I)
        if m:
            payment_details["payment_priority"] = clean_text(m.group(1))
    if payment_details.get("purpose"):
        payment_details["purpose"] = re.sub(r'\s*Дата документа:?\s*$', '', payment_details["purpose"], flags=re.I).strip()
    if not payment_details.get("amount_in_words"):
        m = re.search(r'([А-ЯЁа-яё\-\s]+рубл[а-яё]+,\s*\d{1,2}\s*коп[а-яё]+)', full)
        if m:
            payment_details["amount_in_words"] = clean_text(m.group(1))
    if not payment_details.get("currency_full"):
        payment_details["currency_full"] = "белорусские рубли"

    if not doc.get("signatory", {}).get("name"):
        name = extract_person_name(full)
        if name:
            doc.setdefault("signatory", {})["name"] = name
    return result
