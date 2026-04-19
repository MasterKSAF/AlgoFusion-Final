from __future__ import annotations

import re

from src.modules.runtime_document_parser_common import (
    CYR_TO_LAT,
    MONTHS_RU,
    clean_text,
    cleanup_bank_name,
    extract_bank_account,
    extract_bic,
    extract_company_names,
    extract_kpp,
    extract_tax_id,
    normalize_account,
)
from src.modules.runtime_invoice_header_party_helpers import (
    _invoice_clean_party_address,
    _invoice_header_line_texts,
    _invoice_is_plausible_party_address,
    _invoice_is_plausible_party_name,
    _invoice_strip_markup,
)
from src.modules.runtime_invoice_header_party_parse import (
    _invoice_parse_customer_section,
    _invoice_parse_supplier_section,
)
from src.modules.runtime_invoice_header_text import clean_invoice_date, extract_phone_pretty, cut_basis


def enrich_invoice_header(head, header_text):
    if not header_text:
        return head

    cleaned_header = _invoice_strip_markup(header_text) or header_text
    company_names = extract_company_names(cleaned_header)
    if company_names and not head["supplier"]["name"] and _invoice_is_plausible_party_name(company_names[0]):
        head["supplier"]["name"] = company_names[0]
    if len(company_names) > 1 and not head["customer"]["name"] and _invoice_is_plausible_party_name(company_names[1]):
        head["customer"]["name"] = company_names[1]

    if company_names:
        supplier_name = head["supplier"]["name"] or company_names[0]
        customer_name = head["customer"]["name"] or (company_names[1] if len(company_names) > 1 else None)
        if supplier_name and customer_name and supplier_name in cleaned_header and customer_name in cleaned_header:
            supplier_tail = cleaned_header.split(supplier_name, 1)[1].split(customer_name, 1)[0]
            customer_tail = cleaned_header.split(customer_name, 1)[1]

            if not head["supplier"]["address"]:
                m = re.search(r'^(.*?)(?=,\s*УНП\s*\d{9}|,\s*р/с\s*BY|,\s*в банке|$)', clean_text(supplier_tail or ''), flags=re.I)
                candidate = _invoice_clean_party_address(m.group(1)) if m else None
                if _invoice_is_plausible_party_address(candidate):
                    head["supplier"]["address"] = candidate

            if not head["customer"]["address"]:
                m = re.search(r'^(.*?)(?=,\s*тел\.?|,\s*УНП\s*\d{9}|,\s*КПП\s*\d{9}|\s*Основание:|$)', clean_text(customer_tail or ''), flags=re.I)
                candidate = _invoice_clean_party_address(m.group(1)) if m else None
                if _invoice_is_plausible_party_address(candidate):
                    head["customer"]["address"] = candidate

            if not head["customer"]["phone"]:
                head["customer"]["phone"] = extract_phone_pretty(customer_tail)
            if not head["customer"]["tax_id"]:
                head["customer"]["tax_id"] = extract_tax_id(customer_tail)
            if not head["customer"]["kpp"]:
                head["customer"]["kpp"] = extract_kpp(customer_tail)
            if not head["supplier"]["bank_name"]:
                m = re.search(r'в банке\s*(.*?)(?=,\s*БИК\s*[A-ZА-Я0-9]+|$)', supplier_tail, flags=re.I)
                if m:
                    head["supplier"]["bank_name"] = cleanup_bank_name(m.group(1))
            if not head["supplier"]["bank_account"]:
                head["supplier"]["bank_account"] = extract_bank_account(supplier_tail)
            if not head["supplier"]["bic"]:
                head["supplier"]["bic"] = extract_bic(supplier_tail)
            if not head["supplier"]["tax_id"]:
                head["supplier"]["tax_id"] = extract_tax_id(supplier_tail)

    return head

def parse_invoice_header(header_text, header_lines=None, raw_ocr_items=None):
    out = {
        "invoice_number": None,
        "invoice_date": None,
        "payment_deadline": None,
        "supplier": {
            "name": None, "address": None, "bank_account": None,
            "bank_name": None, "bic": None, "tax_id": None
        },
        "customer": {
            "name": None, "address": None, "tax_id": None,
            "kpp": None, "phone": None
        },
        "basis": None,
    }
    if not header_text:
        return out

    lines = _invoice_header_line_texts(header_lines)

    invoice_line = next((line for line in lines if re.search(r'Счет\s*№', line, flags=re.I)), None)
    scope_for_invoice = invoice_line or header_text
    m = re.search(
        r'Счет\s*№\s*([A-Za-zА-Яа-я0-9\-\/]+)\s*от\s*([0-3]?\d\s+(?:' + MONTHS_RU + r')\s+20\d{2})(?:\s*г\.)?',
        scope_for_invoice,
        flags=re.I
    )
    if m:
        out["invoice_number"] = clean_text(m.group(1))
        out["invoice_date"] = clean_invoice_date(m.group(2))

    basis_line = next((line for line in lines if re.search(r'Основание:', line, flags=re.I)), None)
    if basis_line:
        m = re.search(r'Основание:\s*(.+)', basis_line, flags=re.I)
        if m:
            out["basis"] = cut_basis(clean_text(m.group(1)))
    else:
        m = re.search(r'Основание:\s*(.+)', header_text, flags=re.I)
        if m:
            out["basis"] = cut_basis(clean_text(m.group(1)))

    supplier_vals = _invoice_parse_supplier_section(lines, header_text=header_text, raw_ocr_items=raw_ocr_items)
    for field in ("name", "tax_id", "address"):
        if supplier_vals.get(field):
            out["supplier"][field] = supplier_vals[field]

    def _normalize_invoice_account_candidate(text):
        if not text:
            return None
        s = clean_text(text)
        if not s:
            return None

        s = s.translate(CYR_TO_LAT)

        # OCR sometimes keeps Y-like letters in non-Latin forms, which breaks BY...
        s = (
            s.replace("Ү", "Y")
             .replace("ү", "Y")
             .replace("Ұ", "Y")
             .replace("ұ", "Y")
             .replace("У", "Y")
             .replace("у", "Y")
             .replace("Ў", "Y")
             .replace("ў", "Y")
             .replace("Ј", "J")
             .replace("ј", "J")
        )

        s = s.upper()
        s = re.sub(r'\s+', '', s)
        s = s.replace("О", "0").replace("O", "0")
        s = s.replace("І", "1").replace("I", "1").replace("L", "1")
        return s


    bank_idx = next((i for i, line in enumerate(lines) if 'р/с' in line.lower()), None)
    if bank_idx is not None:
        bank_parts = [lines[bank_idx]]
        if bank_idx + 1 < len(lines):
            bank_parts.append(lines[bank_idx + 1])
        if bank_idx + 2 < len(lines):
            bank_parts.append(lines[bank_idx + 2])

        bank_block = clean_text(" ".join(x for x in bank_parts if x))

        account_match = re.search(r'р/с\s*(.+?)(?=,\s*в банке|\s+в банке|,\s*БИК\b|\s+БИК\b|$)', bank_block, flags=re.I)
        if account_match:
            account_candidate = _normalize_invoice_account_candidate(account_match.group(1))
            m_acc = re.search(r'BY\d{2}[A-Z0-9]{24}', account_candidate or '')
            if m_acc:
                out["supplier"]["bank_account"] = m_acc.group(0)

        if not out["supplier"]["bank_account"]:
            for cand in bank_parts:
                cand_norm = _normalize_invoice_account_candidate(cand)
                m_acc = re.search(r'BY\d{2}[A-Z0-9]{24}', cand_norm or '')
                if m_acc:
                    out["supplier"]["bank_account"] = m_acc.group(0)
                    break

        bank_name_match = re.search(r'в банке\s*(.*?)(?=,\s*БИК\b|\s+БИК\b|$)', bank_block, flags=re.I)
        if bank_name_match:
            out["supplier"]["bank_name"] = cleanup_bank_name(bank_name_match.group(1))

        bic_in_block = extract_bic(bank_block)
        if bic_in_block:
            out["supplier"]["bic"] = bic_in_block
        else:
            for cand in bank_parts:
                cand_clean = clean_text(cand)
                if not cand_clean:
                    continue
                cand_norm = normalize_account(cand_clean)
                if not cand_norm:
                    continue
                m_bic = re.search(r'[A-Z]{6}[A-Z0-9]{2}', cand_norm)
                if m_bic:
                    out["supplier"]["bic"] = m_bic.group(0)
                    break


    customer_vals = _invoice_parse_customer_section(lines, header_text=header_text, raw_ocr_items=raw_ocr_items)
    for field in ("name", "address", "tax_id", "kpp", "phone"):
        if customer_vals.get(field):
            out["customer"][field] = customer_vals[field]

    if not out["customer"]["name"]:
        companies = extract_company_names(header_text)
        if len(companies) > 1:
            out["customer"]["name"] = clean_text(companies[-1])

    return out
